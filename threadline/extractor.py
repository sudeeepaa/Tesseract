"""
Threadline extractor layer.

Extractor (Protocol)
    LLMExtractor  — OpenAI GPT-4o-mini or Gemini Flash.
                    Structured JSON prompt → Pydantic validation → ExtractionResult.
                    3× retry with exponential backoff.
                    Returns partial result on failure rather than raising.
    MockExtractor — Deterministic, fixture-aware, no API key required.
                    Pre-built responses for meeting_01 … meeting_04.
                    Falls back to generic plausible output for unknown IDs.

create_extractor(settings) — factory that auto-selects the right backend.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Protocol, runtime_checkable

from threadline.models import (
    ActionItem,
    ActionItemStatus,
    ConflictRecord,
    Decision,
    DecisionStatus,
    Entity,
    EntityType,
    ExtractionResult,
    ExtractedFact,
    FactType,
    MeetingTranscript,
    PriorDecisionUpdate,
    SupersessionRecord,
    Topic,
    _make_id,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# LLM prompt
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are an expert meeting analyst. Extract structured information from "
    "meeting transcripts and return ONLY valid JSON — no markdown, no explanation."
)


def _build_prompt(transcript: MeetingTranscript, existing: list[Decision]) -> str:
    if existing:
        existing_block = "\n".join(
            f"  [{d.id}] ({d.status.value}) {d.text}" for d in existing
        )
    else:
        existing_block = "  (none — this is the first meeting)"

    return f"""MEETING ID: {transcript.id}
MEETING TITLE: {transcript.meeting_title or "Untitled"}

EXISTING DECISIONS FROM PRIOR MEETINGS:
{existing_block}

TRANSCRIPT:
{transcript.text}

────────────────────────────────────────────────────────────────────────
Return a JSON object with exactly these keys:

{{
  "decisions": [
    {{
      "text": "concise statement of what was decided",
      "status": "<see STATUS GUIDE>",
      "rationale": "why (optional, null ok)",
      "owner": "person responsible (optional, null ok)",
      "supersedes_decision_id": "ID from EXISTING DECISIONS if this replaces one, else null"
    }}
  ],

  "prior_decision_updates": [
    {{
      "decision_id":    "ID from EXISTING DECISIONS list above",
      "decision_text":  "original text of that prior decision",
      "new_status":     "under_review | superseded | reversed",
      "reason":         "why the status is changing",
      "new_decision_id":"ID of the replacement decision (only when new_status=superseded)"
    }}
  ],

  "action_items": [
    {{
      "text":     "specific task",
      "assignee": "person (null ok)",
      "due_date": "YYYY-MM-DD or plain string (null ok)",
      "status":   "open | in_progress | completed | cancelled"
    }}
  ],

  "entities": [
    {{"name": "...", "entity_type": "person|organization|project|date|location|technology"}}
  ],

  "topics": ["string", "..."],

  "conflicts_detected": [
    {{
      "old_decision_id":    "ID from EXISTING DECISIONS",
      "conflict_description": "what exactly conflicts and why"
    }}
  ]
}}

════════════════════════════════════════════════════════════════════════
STATUS GUIDE — assign status carefully:

  proposed      Mentioned as a possible option; NOT yet agreed upon.

  confirmed     Explicitly agreed upon by the group in THIS meeting.

  under_review  ★ A PRIOR decision (from EXISTING DECISIONS) is being
                  QUESTIONED, flagged, or put in doubt — but NO replacement
                  has been confirmed yet. The old decision is still nominally
                  in force; its validity is now uncertain.
                  → Use for meeting_03-style situations: concern raised,
                    no substitute chosen.

  superseded    A PRIOR decision has been EXPLICITLY REPLACED by a NEW
                confirmed decision in THIS meeting. BOTH conditions must hold:
                  (a) the prior decision is acknowledged as no longer valid
                  (b) a specific replacement is explicitly confirmed.
                → Do NOT use if only concerns were raised without a confirmed alt.

  reversed      A prior decision is explicitly cancelled with NO replacement.

CRITICAL RULE:
  "under_review" ≠ "superseded".
  If a problem is flagged but no new decision is locked in, use "under_review".
  Only write "superseded" when the replacement is unambiguously confirmed.

ADDITIONAL RULES:
  1. Only populate prior_decision_updates for IDs present in EXISTING DECISIONS.
  2. conflicts_detected should list even under_review-level concerns.
  3. Return [] for any section with nothing to report — never omit a key.
  4. IDs you generate in "decisions" may be referenced in prior_decision_updates
     as "new_decision_id" within the same response.
════════════════════════════════════════════════════════════════════════
"""


# ─────────────────────────────────────────────────────────────────────────────
# Protocol
# ─────────────────────────────────────────────────────────────────────────────

@runtime_checkable
class Extractor(Protocol):
    def extract(
        self,
        transcript: MeetingTranscript,
        existing_decisions: list[Decision] | None = None,
    ) -> ExtractionResult:
        """Extract structured facts from a meeting transcript."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# LLMExtractor
# ─────────────────────────────────────────────────────────────────────────────

class LLMExtractor:
    """
    Calls OpenAI (GPT-4o-mini) or Gemini Flash and validates the structured
    JSON response against Pydantic models.

    Failure policy: if all retries are exhausted, returns an ExtractionResult
    with extraction_errors populated so the pipeline can continue rather than
    crash.
    """

    def __init__(
        self,
        backend: str = "openai",
        openai_api_key: str = "",
        openai_model: str = "gpt-4o-mini",
        gemini_api_key: str = "",
        gemini_model: str = "gemini-1.5-flash",
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
    ) -> None:
        self.backend = backend
        self.openai_api_key = openai_api_key
        self.openai_model = openai_model
        self.gemini_api_key = gemini_api_key
        self.gemini_model = gemini_model
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self._openai_client = None
        self._gemini_client = None

    # ── LLM call ─────────────────────────────────────────────────────────────

    def _call_openai(self, user_prompt: str) -> str:
        if self._openai_client is None:
            from openai import OpenAI
            self._openai_client = OpenAI(api_key=self.openai_api_key)
        resp = self._openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return resp.choices[0].message.content or ""

    def _call_gemini(self, user_prompt: str) -> str:
        if self._gemini_client is None:
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_api_key)
            self._gemini_client = genai.GenerativeModel(self.gemini_model)
        full = f"{_SYSTEM_PROMPT}\n\n{user_prompt}\n\nReturn only valid JSON."
        raw = self._gemini_client.generate_content(full).text or ""
        # Strip any accidental markdown code fence
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw)
        return raw

    def _call_llm(self, user_prompt: str) -> str:
        if self.backend == "openai":
            return self._call_openai(user_prompt)
        if self.backend == "gemini":
            return self._call_gemini(user_prompt)
        raise ValueError(f"Unknown backend: {self.backend!r}")

    # ── Response parsing ──────────────────────────────────────────────────────

    def _parse(
        self,
        raw: str,
        meeting_id: str,
        existing: list[Decision],
    ) -> ExtractionResult:
        data = json.loads(raw)
        errors: list[str] = []
        existing_by_id = {d.id: d for d in existing}

        # ── decisions ────────────────────────────────────────────────────────
        decisions: list[Decision] = []
        # Keep a local index by position so prior_decision_updates can reference
        # decisions created within the same response.
        local_decisions_by_id: dict[str, Decision] = {}

        for raw_d in data.get("decisions", []):
            try:
                d = Decision(
                    source_meeting_id=meeting_id,
                    text=raw_d["text"],
                    status=DecisionStatus(raw_d.get("status", "confirmed")),
                    rationale=raw_d.get("rationale"),
                    owner=raw_d.get("owner"),
                    supersedes_decision_id=raw_d.get("supersedes_decision_id"),
                )
                decisions.append(d)
                local_decisions_by_id[d.id] = d
            except Exception as exc:
                errors.append(f"Decision parse: {exc} ← {raw_d}")

        # ── prior_decision_updates ────────────────────────────────────────────
        prior_updates: list[PriorDecisionUpdate] = []
        supersessions: list[SupersessionRecord] = []

        for raw_u in data.get("prior_decision_updates", []):
            try:
                old_id      = raw_u.get("decision_id", "")
                old_d       = existing_by_id.get(old_id)
                new_status  = DecisionStatus(raw_u.get("new_status", "under_review"))
                new_dec_id  = raw_u.get("new_decision_id")

                pu = PriorDecisionUpdate(
                    decision_id=old_id,
                    decision_text=raw_u.get("decision_text") or (old_d.text if old_d else ""),
                    new_status=new_status,
                    reason=raw_u.get("reason"),
                    new_decision_id=new_dec_id,
                )
                prior_updates.append(pu)

                # Build SupersessionRecord only when both sides are known
                if new_status == DecisionStatus.superseded and old_d and new_dec_id:
                    new_d = local_decisions_by_id.get(new_dec_id) or existing_by_id.get(new_dec_id)
                    if new_d:
                        supersessions.append(SupersessionRecord(
                            old_decision_id=old_id,
                            new_decision_id=new_dec_id,
                            old_text=old_d.text,
                            new_text=new_d.text,
                            reason=raw_u.get("reason"),
                            meeting_id=meeting_id,
                        ))
            except Exception as exc:
                errors.append(f"PriorDecisionUpdate parse: {exc} ← {raw_u}")

        # ── action_items ──────────────────────────────────────────────────────
        action_items: list[ActionItem] = []
        for raw_ai in data.get("action_items", []):
            try:
                action_items.append(ActionItem(
                    source_meeting_id=meeting_id,
                    text=raw_ai["text"],
                    assignee=raw_ai.get("assignee"),
                    due_date=raw_ai.get("due_date"),
                    status=ActionItemStatus(raw_ai.get("status", "open")),
                ))
            except Exception as exc:
                errors.append(f"ActionItem parse: {exc} ← {raw_ai}")

        # ── entities ──────────────────────────────────────────────────────────
        entities: list[Entity] = []
        for raw_e in data.get("entities", []):
            try:
                entities.append(Entity(
                    name=raw_e["name"],
                    entity_type=EntityType(raw_e.get("entity_type", "technology")),
                    source_meeting_ids=[meeting_id],
                ))
            except Exception as exc:
                errors.append(f"Entity parse: {exc} ← {raw_e}")

        # ── topics ────────────────────────────────────────────────────────────
        topics = [
            Topic(name=str(t), source_meeting_ids=[meeting_id])
            for t in data.get("topics", [])
        ]

        # ── conflicts ─────────────────────────────────────────────────────────
        new_conflicts: list[ConflictRecord] = []
        for raw_c in data.get("conflicts_detected", []):
            old_id = raw_c.get("old_decision_id", "")
            old_d  = existing_by_id.get(old_id)
            if not old_d:
                errors.append(f"ConflictRecord references unknown decision {old_id!r}")
                continue
            try:
                new_conflicts.append(ConflictRecord(
                    fact_a_id=old_id,
                    fact_b_id=meeting_id,
                    fact_a_text=old_d.text,
                    fact_b_text=raw_c.get("conflict_description", ""),
                    description=raw_c.get("conflict_description", ""),
                    meeting_a_id=old_d.source_meeting_id,
                    meeting_b_id=meeting_id,
                    resolved=False,
                ))
            except Exception as exc:
                errors.append(f"ConflictRecord parse: {exc} ← {raw_c}")

        # ── facts (derived) ───────────────────────────────────────────────────
        facts: list[ExtractedFact] = []
        for d in decisions:
            facts.append(ExtractedFact(
                claim_text=d.text,
                fact_type=FactType.decision,
                source_meeting_id=meeting_id,
                ref_id=d.id,
                confidence=0.95,
            ))
        for ai in action_items:
            facts.append(ExtractedFact(
                claim_text=ai.text,
                fact_type=FactType.action_item,
                source_meeting_id=meeting_id,
                ref_id=ai.id,
                confidence=0.95,
            ))

        return ExtractionResult(
            meeting_id=meeting_id,
            decisions=decisions,
            prior_decision_updates=prior_updates,
            action_items=action_items,
            entities=entities,
            topics=topics,
            facts=facts,
            new_conflicts=new_conflicts,
            supersessions=supersessions,
            extraction_errors=errors,
            raw_llm_response=raw,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def extract(
        self,
        transcript: MeetingTranscript,
        existing_decisions: list[Decision] | None = None,
    ) -> ExtractionResult:
        existing = existing_decisions or []
        prompt   = _build_prompt(transcript, existing)
        last_err = ""

        for attempt in range(self.max_retries):
            try:
                raw    = self._call_llm(prompt)
                result = self._parse(raw, transcript.id, existing)
                if attempt > 0:
                    logger.info("Extraction succeeded on attempt %d", attempt + 1)
                return result
            except json.JSONDecodeError as exc:
                last_err = f"JSON decode (attempt {attempt + 1}): {exc}"
                logger.warning(last_err)
            except Exception as exc:
                last_err = f"{type(exc).__name__} (attempt {attempt + 1}): {exc}"
                logger.warning(last_err)

            if attempt < self.max_retries - 1:
                delay = self.retry_base_delay * (2 ** attempt)
                logger.info("Retrying in %.1fs…", delay)
                time.sleep(delay)

        logger.error("Extraction failed after %d attempts: %s", self.max_retries, last_err)
        return ExtractionResult(
            meeting_id=transcript.id,
            extraction_errors=[f"Extraction failed ({self.max_retries} attempts): {last_err}"],
        )


# ─────────────────────────────────────────────────────────────────────────────
# MockExtractor — fixture-aware, deterministic, zero network calls
# ─────────────────────────────────────────────────────────────────────────────

# Pre-built static responses for the four demo fixtures.
# IDs are hardcoded so cross-meeting references (supersessions, conflicts) work
# consistently whether the LLM or Mock extractor is used.
_MEETING_01_DECISIONS = [
    Decision(id="dec_m1_01", text="Use React for the frontend",
             status=DecisionStatus.confirmed, owner="Dev Rao",
             source_meeting_id="meeting_01",
             rationale="Team familiarity and ecosystem maturity"),
    Decision(id="dec_m1_02", text="Use FastAPI for the backend",
             status=DecisionStatus.confirmed, owner="Dev Rao",
             source_meeting_id="meeting_01"),
    Decision(id="dec_m1_03", text="Use PostgreSQL for primary storage",
             status=DecisionStatus.confirmed, owner="Dev Rao",
             source_meeting_id="meeting_01"),
    Decision(id="dec_m1_04", text="Use Auth0 for authentication",
             status=DecisionStatus.confirmed, owner="Dev Rao",
             source_meeting_id="meeting_01",
             rationale="Existing enterprise contract covers this"),
    Decision(id="dec_m1_05", text="Ship V1 by June 30 (non-negotiable)",
             status=DecisionStatus.confirmed, owner="Marcus Webb",
             source_meeting_id="meeting_01"),
    Decision(id="dec_m1_06", text="All data must remain in EU region (AWS eu-west-1)",
             status=DecisionStatus.confirmed, owner="Marcus Webb",
             source_meeting_id="meeting_01"),
    Decision(id="dec_m1_07", text="Use Material UI component library for V1",
             status=DecisionStatus.confirmed, owner="Dev Rao",
             source_meeting_id="meeting_01"),
]

_MEETING_02_DECISIONS = [
    Decision(id="dec_m2_01", text="Switch primary storage from PostgreSQL to MongoDB Atlas",
             status=DecisionStatus.confirmed, owner="Lena Hoffmann",
             source_meeting_id="meeting_02",
             supersedes_decision_id="dec_m1_03",
             rationale="Better fit for hierarchical data model; earlier Postgres decision was a mistake"),
]

_MEETING_04_DECISIONS = [
    Decision(id="dec_m4_01",
             text="Switch authentication from Auth0 to Keycloak (self-hosted in eu-west-1)",
             status=DecisionStatus.confirmed, owner="Dev Rao",
             source_meeting_id="meeting_04",
             supersedes_decision_id="dec_m1_04",
             rationale="Auth0 standard tier violates GDPR; Private Cloud too expensive; Keycloak migration is 4 dev-days"),
]

_MOCK_RESPONSES: dict[str, dict] = {
    "meeting_01": {
        "decisions": _MEETING_01_DECISIONS,
        "prior_decision_updates": [],
        "action_items": [
            ActionItem(id="ai_m1_01", text="Deliver wireframes",
                       assignee="Priya Nair", due_date="2024-03-18",
                       status=ActionItemStatus.open, source_meeting_id="meeting_01"),
            ActionItem(id="ai_m1_02", text="Scaffold repo and set up CI pipeline",
                       assignee="Dev Rao", due_date="2024-03-08",
                       status=ActionItemStatus.open, source_meeting_id="meeting_01"),
        ],
        "entities": [
            Entity(id="ent_sarah",  name="Sarah Chen",  entity_type=EntityType.person,       source_meeting_ids=["meeting_01"]),
            Entity(id="ent_dev",    name="Dev Rao",     entity_type=EntityType.person,       source_meeting_ids=["meeting_01"]),
            Entity(id="ent_marcus", name="Marcus Webb", entity_type=EntityType.person,       source_meeting_ids=["meeting_01"]),
            Entity(id="ent_priya",  name="Priya Nair",  entity_type=EntityType.person,       source_meeting_ids=["meeting_01"]),
            Entity(id="ent_auth0",  name="Auth0",       entity_type=EntityType.technology,   source_meeting_ids=["meeting_01"]),
            Entity(id="ent_react",  name="React",       entity_type=EntityType.technology,   source_meeting_ids=["meeting_01"]),
            Entity(id="ent_fastapi",name="FastAPI",     entity_type=EntityType.technology,   source_meeting_ids=["meeting_01"]),
            Entity(id="ent_pg",     name="PostgreSQL",  entity_type=EntityType.technology,   source_meeting_ids=["meeting_01"]),
        ],
        "topics": ["Tech stack selection", "Authentication", "Project timeline", "GDPR compliance", "Component library"],
        "conflicts": [],
    },
    "meeting_02": {
        "decisions": _MEETING_02_DECISIONS,
        "prior_decision_updates": [
            PriorDecisionUpdate(
                decision_id="dec_m1_03",
                decision_text="Use PostgreSQL for primary storage",
                new_status=DecisionStatus.superseded,
                reason="Data model evolved; MongoDB Atlas is a better fit for hierarchical structures",
                new_decision_id="dec_m2_01",
            ),
        ],
        "action_items": [
            ActionItem(id="ai_m2_01", text="Set up MongoDB Atlas cluster in eu-west-1",
                       assignee="Lena Hoffmann", due_date="2024-04-14",
                       status=ActionItemStatus.open, source_meeting_id="meeting_02"),
            ActionItem(id="ai_m2_02", text="Update README and architecture docs to reflect MongoDB",
                       assignee="Dev Rao", due_date="2024-04-12",
                       status=ActionItemStatus.open, source_meeting_id="meeting_02"),
            ActionItem(id="ai_m2_03", text="Freeze data model by end of sprint",
                       assignee="Dev Rao", due_date="2024-04-12",
                       status=ActionItemStatus.open, source_meeting_id="meeting_02"),
        ],
        "entities": [
            Entity(id="ent_lena",  name="Lena Hoffmann", entity_type=EntityType.person,     source_meeting_ids=["meeting_02"]),
            Entity(id="ent_mongo", name="MongoDB Atlas",  entity_type=EntityType.technology, source_meeting_ids=["meeting_02"]),
        ],
        "topics": ["Sprint review", "Database migration", "Data model", "Project timeline"],
        "conflicts": [],
    },
    "meeting_03": {
        # No new confirmed decisions — Auth0 concern raised but no replacement chosen.
        # Auth0 → under_review (NOT superseded).  This is the critical test case.
        "decisions": [],
        "prior_decision_updates": [
            PriorDecisionUpdate(
                decision_id="dec_m1_04",
                decision_text="Use Auth0 for authentication",
                new_status=DecisionStatus.under_review,   # ← must NOT be superseded
                reason="Auth0 standard tier has GDPR carve-outs; telemetry may route through US infrastructure",
            ),
        ],
        "action_items": [
            ActionItem(id="ai_m3_01", text="Scope Keycloak migration effort and produce estimate",
                       assignee="Dev Rao", due_date="2024-05-08",
                       status=ActionItemStatus.open, source_meeting_id="meeting_03"),
            ActionItem(id="ai_m3_02", text="Schedule Marcus + Raj call to review Auth0 GDPR issue",
                       assignee="Sarah Chen", due_date="2024-05-09",
                       status=ActionItemStatus.open, source_meeting_id="meeting_03"),
            ActionItem(id="ai_m3_03", text="Send Keycloak migration guide to Dev",
                       assignee="Raj Patel", due_date="2024-05-07",
                       status=ActionItemStatus.open, source_meeting_id="meeting_03"),
        ],
        "entities": [
            Entity(id="ent_raj",      name="Raj Patel",  entity_type=EntityType.person,     source_meeting_ids=["meeting_03"]),
            Entity(id="ent_keycloak", name="Keycloak",   entity_type=EntityType.technology,  source_meeting_ids=["meeting_03"]),
        ],
        "topics": ["Security review", "GDPR compliance", "Authentication provider", "Keycloak evaluation"],
        # Conflict: existing Auth0 decision vs GDPR obligations
        "conflicts": [
            ConflictRecord(
                id="conflict_01",
                fact_a_id="dec_m1_04",
                fact_b_id="ai_m3_02",
                fact_a_text="Use Auth0 for authentication",
                fact_b_text="Auth0 standard tier GDPR compliance is insufficient for EU data obligations",
                description=(
                    "Auth0 (meeting_01) conflicts with GDPR obligations: "
                    "standard tier telemetry routes through US infrastructure, "
                    "violating EU data residency requirements agreed in meeting_01"
                ),
                meeting_a_id="meeting_01",
                meeting_b_id="meeting_03",
                resolved=False,
            )
        ],
    },
    "meeting_04": {
        "decisions": _MEETING_04_DECISIONS,
        "prior_decision_updates": [
            PriorDecisionUpdate(
                decision_id="dec_m1_04",
                decision_text="Use Auth0 for authentication",
                new_status=DecisionStatus.superseded,   # ← now superseded (replacement confirmed)
                reason="Keycloak explicitly chosen by Marcus; Auth0 Private Cloud too expensive",
                new_decision_id="dec_m4_01",
            ),
        ],
        "action_items": [
            ActionItem(id="ai_m4_01", text="Keycloak running in dev environment",
                       assignee="Dev Rao", due_date="2024-05-16",
                       status=ActionItemStatus.open, source_meeting_id="meeting_04"),
            ActionItem(id="ai_m4_02", text="Keycloak production-ready",
                       assignee="Dev Rao", due_date="2024-05-20",
                       status=ActionItemStatus.open, source_meeting_id="meeting_04"),
            ActionItem(id="ai_m4_03", text="Security spot check on Keycloak deployment",
                       assignee="Raj Patel", due_date="2024-05-21",
                       status=ActionItemStatus.open, source_meeting_id="meeting_04"),
            ActionItem(id="ai_m4_04", text="Send Priya Keycloak login page mockup by Monday",
                       assignee="Dev Rao", due_date="2024-05-19",
                       status=ActionItemStatus.open, source_meeting_id="meeting_04"),
        ],
        "entities": [],
        "topics": ["Authentication decision", "Keycloak deployment", "Launch readiness", "Security review"],
        "conflicts": [],
    },
}


class MockExtractor:
    """
    Deterministic extractor — no API calls, no network, always fast.

    For the four fixture meeting IDs (meeting_01 … meeting_04) it returns
    pre-built, internally consistent data that drives the full supersession
    and conflict-resolution story the demo needs.

    For any other meeting_id it returns plausible generic output.
    """

    def extract(
        self,
        transcript: MeetingTranscript,
        existing_decisions: list[Decision] | None = None,
    ) -> ExtractionResult:
        meeting_id = transcript.id
        mock       = _MOCK_RESPONSES.get(meeting_id)
        existing   = existing_decisions or []

        if mock:
            return self._build_from_mock(meeting_id, mock, existing)
        return self._build_generic(transcript)

    def _build_from_mock(
        self,
        meeting_id: str,
        mock: dict,
        existing: list[Decision],
    ) -> ExtractionResult:
        decisions:       list[Decision]            = mock.get("decisions", [])
        prior_updates:   list[PriorDecisionUpdate] = mock.get("prior_decision_updates", [])
        action_items:    list[ActionItem]           = mock.get("action_items", [])
        entities:        list[Entity]               = mock.get("entities", [])
        topic_names:     list[str]                  = mock.get("topics", [])
        raw_conflicts:   list[ConflictRecord]       = mock.get("conflicts", [])

        existing_by_id = {d.id: d for d in existing}

        # Build SupersessionRecords from prior_updates
        supersessions: list[SupersessionRecord] = []
        for pu in prior_updates:
            if pu.new_status == DecisionStatus.superseded and pu.new_decision_id:
                old_d = existing_by_id.get(pu.decision_id)
                new_d = next((d for d in decisions if d.id == pu.new_decision_id), None)
                if old_d and new_d:
                    supersessions.append(SupersessionRecord(
                        old_decision_id=pu.decision_id,
                        new_decision_id=pu.new_decision_id,
                        old_text=old_d.text,
                        new_text=new_d.text,
                        reason=pu.reason,
                        meeting_id=meeting_id,
                    ))

        # Resolve conflicts that were pre-built in a previous meeting
        # meeting_04 resolves conflict_01 from meeting_03
        resolved_conflicts: list[ConflictRecord] = []
        if meeting_id == "meeting_04":
            resolved_conflicts = [
                ConflictRecord(
                    id="conflict_01",
                    fact_a_id="dec_m1_04",
                    fact_b_id="ai_m3_02",
                    fact_a_text="Use Auth0 for authentication",
                    fact_b_text="Auth0 standard tier GDPR compliance is insufficient",
                    description="Auth0 GDPR conflict resolved: Keycloak selected as replacement",
                    meeting_a_id="meeting_01",
                    meeting_b_id="meeting_03",
                    resolved=True,
                    resolution_meeting_id="meeting_04",
                )
            ]

        # Derive ExtractedFacts for vector store
        facts: list[ExtractedFact] = []
        for d in decisions:
            facts.append(ExtractedFact(
                claim_text=d.text, fact_type=FactType.decision,
                source_meeting_id=meeting_id, ref_id=d.id, confidence=0.99,
            ))
        for ai in action_items:
            facts.append(ExtractedFact(
                claim_text=ai.text, fact_type=FactType.action_item,
                source_meeting_id=meeting_id, ref_id=ai.id, confidence=0.99,
            ))

        topics = [Topic(name=t, source_meeting_ids=[meeting_id]) for t in topic_names]

        return ExtractionResult(
            meeting_id=meeting_id,
            decisions=decisions,
            prior_decision_updates=prior_updates,
            action_items=action_items,
            entities=entities,
            topics=topics,
            facts=facts,
            new_conflicts=raw_conflicts + resolved_conflicts,
            supersessions=supersessions,
        )

    def _build_generic(self, transcript: MeetingTranscript) -> ExtractionResult:
        mid = transcript.id
        d = Decision(
            text=f"Proceed with the approach discussed in {mid}",
            status=DecisionStatus.confirmed,
            source_meeting_id=mid,
        )
        ai = ActionItem(
            text=f"Follow up on items from {mid}",
            source_meeting_id=mid,
        )
        return ExtractionResult(
            meeting_id=mid,
            decisions=[d],
            action_items=[ai],
            topics=[Topic(name="General discussion", source_meeting_ids=[mid])],
            facts=[
                ExtractedFact(claim_text=d.text,  fact_type=FactType.decision,    source_meeting_id=mid, ref_id=d.id,  confidence=0.5),
                ExtractedFact(claim_text=ai.text, fact_type=FactType.action_item, source_meeting_id=mid, ref_id=ai.id, confidence=0.5),
            ],
        )


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

def create_extractor(settings) -> Extractor:
    """
    Instantiate the correct Extractor implementation.
    Falls back to MockExtractor when the configured backend has no API key.
    """
    backend = settings.effective_extractor_backend

    if backend.value == "mock":
        logger.warning(
            "Using MockExtractor — no API key configured or EXTRACTOR_BACKEND=mock. "
            "The briefing will show demo data, not real LLM extraction."
        )
        return MockExtractor()

    if backend.value == "openai":
        return LLMExtractor(
            backend="openai",
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
        )

    if backend.value == "gemini":
        return LLMExtractor(
            backend="gemini",
            gemini_api_key=settings.gemini_api_key,
            gemini_model=settings.gemini_model,
        )

    raise ValueError(f"Unknown extractor backend: {backend!r}")
