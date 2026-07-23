"""
Threadline data contracts.

All inter-component types are defined here and ONLY here.
No business logic lives in this module — only data shapes and their invariants.

Design notes
────────────
• Every model carries source_meeting_id so lineage is always traceable.
• DecisionStatus has five states; the under_review → superseded transition
  is the key mechanism for conflict-then-resolution storytelling.
• StageEvent is what the pipeline yields; the FastAPI SSE endpoint
  forwards each one verbatim to the browser.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_id() -> str:
    """Short random ID used as default for all model instances."""
    return str(uuid.uuid4())[:8]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────

class DecisionStatus(str, Enum):
    """
    Lifecycle states for a Decision node.

    The state machine is:
        proposed  ──► confirmed ──► under_review ──► superseded
                  └──► confirmed ──► reversed
                  └──► confirmed (stays confirmed if never challenged)

    under_review is distinct from superseded:
        • under_review  = flagged as problematic, no replacement yet confirmed.
        • superseded    = explicitly replaced by a NEW confirmed decision.
        • reversed      = cancelled outright, no replacement.

    meeting_03 → Auth0 becomes under_review (GDPR concern raised, no alt chosen)
    meeting_04 → Auth0 becomes superseded  (Keycloak explicitly confirmed)
    """
    proposed     = "proposed"
    confirmed    = "confirmed"
    under_review = "under_review"
    superseded   = "superseded"
    reversed     = "reversed"


class ActionItemStatus(str, Enum):
    open        = "open"
    in_progress = "in_progress"
    completed   = "completed"
    cancelled   = "cancelled"


class FactType(str, Enum):
    decision    = "decision"
    action_item = "action_item"
    entity      = "entity"
    topic       = "topic"
    general     = "general"


class EntityType(str, Enum):
    person       = "person"
    organization = "organization"
    project      = "project"
    date         = "date"
    location     = "location"
    technology   = "technology"


class PipelineStage(str, Enum):
    """Ordered stages emitted as SSE events during a pipeline run."""
    INGEST       = "INGEST"
    TRANSCRIBE   = "TRANSCRIBE"
    EXTRACT      = "EXTRACT"
    GRAPH_WRITE  = "GRAPH_WRITE"
    VECTOR_WRITE = "VECTOR_WRITE"
    BRIEFING     = "BRIEFING"
    PIPELINE     = "PIPELINE"   # synthetic — emitted once at the very end


class StageStatus(str, Enum):
    pending = "pending"
    running = "running"
    done    = "done"
    error   = "error"
    skipped = "skipped"


class NodeType(str, Enum):
    meeting     = "meeting"
    decision    = "decision"
    action_item = "action_item"
    entity      = "entity"
    topic       = "topic"


class EdgeType(str, Enum):
    supersedes   = "SUPERSEDES"
    contradicts  = "CONTRADICTS"
    mentioned_in = "MENTIONED_IN"
    assigned_to  = "ASSIGNED_TO"
    related_to   = "RELATED_TO"
    resolves     = "RESOLVES"


# ─────────────────────────────────────────────────────────────────────────────
# Core domain models
# ─────────────────────────────────────────────────────────────────────────────

class MeetingTranscript(BaseModel):
    """Raw meeting input, before extraction."""
    id:            str            = Field(default_factory=_make_id)
    source_file:   str
    text:          str
    recorded_at:   Optional[datetime] = None
    meeting_title: Optional[str]      = None

    model_config = {"frozen": False}


class Decision(BaseModel):
    """
    A resolved or in-progress decision from a meeting.

    supersedes_decision_id points to a Decision in a PRIOR meeting that this
    one explicitly replaces.  The GraphStore creates a SUPERSEDES edge between
    the two nodes when it sees this field populated.
    """
    id:                      str            = Field(default_factory=_make_id)
    text:                    str
    status:                  DecisionStatus = DecisionStatus.confirmed
    rationale:               Optional[str]  = None
    owner:                   Optional[str]  = None
    source_meeting_id:       str
    supersedes_decision_id:  Optional[str]  = None
    contradicts_decision_ids: list[str]     = Field(default_factory=list)
    # Why this decision's status last changed (e.g. the reason it went
    # under_review or was superseded). Surfaced as the explainability trace.
    status_reason:           Optional[str]  = None

    def is_active(self) -> bool:
        """True when the decision is still in effect (not superseded/reversed)."""
        return self.status in (
            DecisionStatus.confirmed,
            DecisionStatus.proposed,
            DecisionStatus.under_review,
        )


class ActionItem(BaseModel):
    """A task assigned during a meeting."""
    id:                   str               = Field(default_factory=_make_id)
    text:                 str
    assignee:             Optional[str]     = None
    due_date:             Optional[str]     = None
    status:               ActionItemStatus  = ActionItemStatus.open
    source_meeting_id:    str
    completed_meeting_id: Optional[str]     = None
    confidence:           float             = 1.0
    reasoning:            Optional[str]     = None
    is_stale:             bool              = False

    @field_validator("due_date", "assignee", mode="before")
    @classmethod
    def _blank_to_none(cls, v: Any) -> Any:
        """Coerce placeholder strings the LLM sometimes emits into None so the
        UI never shows a literal 'null' due date."""
        if isinstance(v, str) and v.strip().lower() in {"null", "none", "", "n/a", "tbd", "undefined"}:
            return None
        return v


class Entity(BaseModel):
    """A named entity referenced across one or more meetings."""
    id:                  str         = Field(default_factory=_make_id)
    name:                str
    entity_type:         EntityType
    source_meeting_ids:  list[str]   = Field(default_factory=list)


class Topic(BaseModel):
    """A discussion topic that may span multiple meetings."""
    id:                 str       = Field(default_factory=_make_id)
    name:               str
    source_meeting_ids: list[str] = Field(default_factory=list)


class ExtractedFact(BaseModel):
    """
    An atomic claim from a meeting.  Each fact becomes exactly one vector
    chunk in the VectorStore.  The ref_id points to a Decision or ActionItem
    for richer metadata on search results.
    """
    id:                str          = Field(default_factory=_make_id)
    claim_text:        str
    speaker:           Optional[str] = None
    fact_type:         FactType      = FactType.general
    confidence:        float         = Field(default=1.0, ge=0.0, le=1.0)
    source_meeting_id: str
    ref_id:            Optional[str] = None


class PriorDecisionUpdate(BaseModel):
    """
    A status change to a decision from a PRIOR meeting, detected in the
    current meeting's transcript.

    This is how the Extractor signals the GraphStore that an existing node
    needs its status field mutated.  The GraphStore also creates a
    SUPERSEDES or CONTRADICTS edge as appropriate.
    """
    decision_id:    str            # ID of the prior decision
    decision_text:  str            # original text (for display, not mutation)
    new_status:     DecisionStatus
    reason:         Optional[str]  = None
    new_decision_id: Optional[str] = None  # populated when new_status == superseded


class ConflictRecord(BaseModel):
    """A detected contradiction between two facts or decisions."""
    id:                    str           = Field(default_factory=_make_id)
    fact_a_id:             str
    fact_b_id:             str
    fact_a_text:           str
    fact_b_text:           str
    description:           str
    meeting_a_id:          str
    meeting_b_id:          str
    resolved:              bool          = False
    resolution_meeting_id: Optional[str] = None
    confidence:            float         = 1.0
    reasoning:             Optional[str] = None
    # ── Human-in-the-loop resolution (set when a user resolves via the UI) ────
    resolution_choice:     Optional[str]      = None   # "keep" | "switch" | "review" | "dismiss"
    resolution_note:       Optional[str]      = None
    resolved_by:           Optional[str]      = None
    resolved_at:           Optional[datetime] = None


class ConflictResolutionRequest(BaseModel):
    """
    Body for POST /api/v1/conflicts/{id}/resolve — a human deciding how to
    settle a flagged contradiction.

    choice semantics:
      • "keep"    — keep the current decision as-is; conflict resolved.
      • "switch"  — replace old with new: supersede_decision_id → superseded,
                    keep_decision_id → confirmed; conflict resolved.
      • "review"  — flag for later: the challenged decision → under_review,
                    conflict stays OPEN (not resolved) with the note attached.
      • "dismiss" — resolve with no status change (mark as not a real conflict).
    """
    choice:                str
    note:                  Optional[str] = None
    resolved_by:           Optional[str] = None
    keep_decision_id:      Optional[str] = None
    supersede_decision_id: Optional[str] = None


class SupersessionRecord(BaseModel):
    """Records that new_decision explicitly supersedes old_decision."""
    id:               str           = Field(default_factory=_make_id)
    old_decision_id:  str
    new_decision_id:  str
    old_text:         str
    new_text:         str
    reason:           Optional[str] = None
    meeting_id:       str           # meeting where the supersession was confirmed


# ─────────────────────────────────────────────────────────────────────────────
# Extraction output
# ─────────────────────────────────────────────────────────────────────────────

class ExtractionResult(BaseModel):
    """
    Complete output of one extraction pass over a single transcript.

    The pipeline consumes this object to drive all downstream writes:
        decisions + prior_decision_updates  → GraphStore
        facts                               → VectorStore
        new_conflicts + supersessions       → GraphStore (relationship edges)
    """
    meeting_id:            str
    decisions:             list[Decision]            = Field(default_factory=list)
    prior_decision_updates: list[PriorDecisionUpdate] = Field(default_factory=list)
    action_items:          list[ActionItem]           = Field(default_factory=list)
    entities:              list[Entity]               = Field(default_factory=list)
    topics:                list[Topic]                = Field(default_factory=list)
    facts:                 list[ExtractedFact]        = Field(default_factory=list)
    new_conflicts:         list[ConflictRecord]       = Field(default_factory=list)
    supersessions:         list[SupersessionRecord]   = Field(default_factory=list)
    extraction_errors:     list[str]                  = Field(default_factory=list)
    extracted_at:          datetime                   = Field(default_factory=_now)
    raw_llm_response:      Optional[str]              = None


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline streaming types
# ─────────────────────────────────────────────────────────────────────────────

class StageEvent(BaseModel):
    """
    Emitted by Pipeline.run_streaming() at each stage transition.
    The FastAPI SSE endpoint serialises each event to JSON and sends it
    as a text/event-stream chunk.
    """
    stage:   PipelineStage
    status:  StageStatus
    message: str
    data:    Optional[dict[str, Any]] = None


class PipelineResult(BaseModel):
    """Aggregate outcome of a complete pipeline run."""
    meeting_id:        str
    stage_events:      list[StageEvent]          = Field(default_factory=list)
    overall_success:   bool                       = True
    extraction_result: Optional[ExtractionResult] = None
    graph_success:     bool                       = False
    vector_success:    bool                       = False
    briefing_success:  bool                       = False
    errors:            list[str]                  = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Graph visualisation types (consumed by the /api/v1/graph endpoint)
# ─────────────────────────────────────────────────────────────────────────────

class GraphNode(BaseModel):
    id:         str
    label:      str
    type:       NodeType
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source:     str
    target:     str
    type:       EdgeType
    superseded: bool           = False   # True → render dashed/greyed in UI
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphSnapshot(BaseModel):
    nodes:        list[GraphNode] = Field(default_factory=list)
    edges:        list[GraphEdge] = Field(default_factory=list)
    generated_at: datetime        = Field(default_factory=_now)


# ─────────────────────────────────────────────────────────────────────────────
# Search / Briefing output types
# ─────────────────────────────────────────────────────────────────────────────

class SearchResult(BaseModel):
    fact_id:   str
    text:      str
    score:     float     = Field(ge=0.0, le=1.0)
    meeting_id: str
    speaker:   Optional[str] = None
    fact_type: FactType       = FactType.general


class BriefingOutput(BaseModel):
    """Structured briefing consumed by both the API and the React frontend."""
    generated_at:  datetime          = Field(default_factory=_now)
    meeting_count: int               = 0
    decisions:     list[Decision]    = Field(default_factory=list)
    action_items:  list[ActionItem]  = Field(default_factory=list)
    conflicts:     list[ConflictRecord] = Field(default_factory=list)
    topics:        list[str]         = Field(default_factory=list)
    markdown:      str               = ""


class MeetingSummary(BaseModel):
    """Per-meeting rollup for the meetings dashboard (counts + metadata)."""
    id:                str
    title:             str
    recorded_at:       Optional[datetime] = None
    ingested_at:       Optional[datetime] = None
    decision_count:    int = 0
    action_item_count: int = 0
    topic_count:       int = 0
    preview:           Optional[str] = None   # short snippet of the transcript
    summary:           Optional[str] = None   # cached LLM summary (generated at ingestion)
