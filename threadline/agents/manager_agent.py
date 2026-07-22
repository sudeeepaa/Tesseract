"""
Manager Agent — Lyzr Studio primary + Google ADK RemoteA2aAgent fallback.

Decision 1 (from v2 plan): Hybrid approach.
  - Primary: Lyzr Studio (real API key, actual delegation workflow)
  - Fallback: Pure ADK with RemoteA2aAgent orchestration (if Lyzr unreachable)
  - Both paths built and tested, graceful-degradation same pattern as stores.

Decision 4 (from v2 plan): Single-process A2A (ASGI sub-mounts).
  - Real A2A HTTP semantics between agents within one process.
  - No five independently-failing services on demo day.

Correlation ID (Phase 13 preview): generated at input and propagated through
every delegation so logs are traceable across agents.

Response flow: Manager → [Input→Extraction→GraphWriter→SemanticMemory→Briefing]
                            (via A2A)          → Manager → Frontend
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Generator

from threadline.models import (
    BriefingOutput,
    ExtractionResult,
    MeetingTranscript,
    PipelineResult,
    PipelineStage,
    StageEvent,
    StageStatus,
)
from threadline.mcp.graph_mcp import (
    graph_upsert_extraction,
    graph_get_all_decisions,
)
from threadline.mcp.vector_mcp import vector_upsert_chunks

logger = logging.getLogger(__name__)

AGENT_NAME = "manager_agent"
AGENT_DESCRIPTION = (
    "Orchestrates the full Tesseract meeting intelligence pipeline. "
    "Delegates to Input, Extraction, Graph Writer, Semantic Memory, and Briefing agents "
    "via A2A protocol. Primary: Lyzr Studio. Fallback: Google ADK RemoteA2aAgent."
)


# ─────────────────────────────────────────────────────────────────────────────
# Lyzr primary path
# ─────────────────────────────────────────────────────────────────────────────

# Default Lyzr Studio synchronous inference endpoint (overridable via LYZR_BASE_URL).
LYZR_INFERENCE_URL = "https://agent-prod.studio.lyzr.ai/v3/inference/chat/"


def _lyzr_ready() -> bool:
    """True when both the Lyzr API key and a target agent id are configured."""
    return bool(os.environ.get("LYZR_API_KEY") and os.environ.get("LYZR_AGENT_ID"))


def _lyzr_extract(
    meeting_id: str,
    transcript_text: str,
    meeting_title: str,
    existing_decisions_json: str,
    correlation_id: str,
):
    """
    Delegate fact extraction to a Lyzr Studio agent — the real, mandatory Lyzr
    integration. The transcript plus our extraction prompt are sent to a
    pre-configured Studio agent whose JSON reply is parsed into an
    ``ExtractionResult``. The caller then persists that result to the local
    graph/vector stores (hosted Lyzr cannot reach our Neo4j/Qdrant, so the
    reasoning is Lyzr's while orchestration/persistence stays in-process).

    Returns the ``ExtractionResult`` on success, or ``None`` to signal the
    caller to fall back to the in-process Gemini/ADK or mock path.
    """
    api_key = os.environ.get("LYZR_API_KEY", "")
    agent_id = os.environ.get("LYZR_AGENT_ID", "")
    if not (api_key and agent_id):
        return None

    try:
        import httpx
        from threadline.extractor import _build_prompt, _SYSTEM_PROMPT, LLMExtractor
        from threadline.models import Decision

        existing: list = []
        try:
            existing = [Decision.model_validate(d)
                        for d in json.loads(existing_decisions_json or "[]")]
        except Exception:
            pass

        transcript = MeetingTranscript(
            id=meeting_id, source_file=f"{meeting_id}.txt",
            text=transcript_text, meeting_title=meeting_title or meeting_id,
        )
        message = (
            f"{_SYSTEM_PROMPT}\n\n{_build_prompt(transcript, existing)}\n\n"
            "Return only the valid JSON object described above — no prose, no code fences."
        )

        url = os.environ.get("LYZR_BASE_URL", LYZR_INFERENCE_URL)
        payload = {
            "user_id": os.environ.get("LYZR_USER_ID", "threadline@tesseract.ai"),
            "agent_id": agent_id,
            "session_id": f"{meeting_id}-{correlation_id}",
            "message": message,
        }
        headers = {
            "Content-Type": "application/json",
            "accept": "application/json",
            "x-api-key": api_key,
        }

        logger.info("[%s] Delegating extraction to Lyzr Studio agent %s", correlation_id, agent_id)
        resp = httpx.post(url, json=payload, headers=headers, timeout=90.0)
        resp.raise_for_status()
        body = resp.json()
        raw = body.get("response") if isinstance(body, dict) else None
        if not raw:
            logger.warning("[%s] Lyzr returned no 'response' text — falling back", correlation_id)
            return None

        result = LLMExtractor()._parse(raw, meeting_id, existing)

        # Guard against a misconfigured Studio agent: if the reply parsed but
        # carries no usable extraction (e.g. a template agent returning its own
        # unrelated JSON), treat it as a failure so the caller falls back to the
        # in-process Gemini/ADK path rather than persisting an empty result.
        if not (result.decisions or result.action_items or result.entities
                or result.topics or result.facts):
            logger.warning(
                "[%s] Lyzr returned no usable extraction (agent may be misconfigured — "
                "see docs/LYZR_SETUP.md) — falling back to Gemini/ADK", correlation_id)
            return None

        logger.info("[%s] Lyzr orchestration complete: %d decisions, %d conflict(s)",
                    correlation_id, len(result.decisions), len(result.new_conflicts))
        return result

    except ImportError:
        logger.info("[%s] httpx unavailable — falling back from Lyzr path", correlation_id)
        return None
    except Exception as exc:
        logger.warning(
            "[%s] Lyzr extraction failed (%s) — falling back to ADK/LLM path",
            correlation_id, exc,
        )
        return None


# ─────────────────────────────────────────────────────────────────────────────
# ADK RemoteA2aAgent fallback path (in-process)
# ─────────────────────────────────────────────────────────────────────────────

def _adk_orchestrate(
    meeting_id: str,
    source_file: str,
    transcript_text: str,
    meeting_title: str,
    correlation_id: str,
    content: bytes | None = None,
) -> tuple[ExtractionResult | None, BriefingOutput | None, list[str], str]:
    """
    Orchestrate the pipeline via in-process agent runners, persisting to the
    local graph/vector stores. Extraction may be delegated to Lyzr Studio; graph
    write, vector index, and briefing always run in-process here.

    Uses the Runner classes directly (not HTTP A2A) to avoid startup overhead in test/mock mode.
    When A2A servers are running (Phase 6 full deployment), this would use RemoteA2aAgent instead.

    Returns:
        (extraction_result, briefing_output, errors, mode)
        where mode ∈ {"lyzr", "adk", "mock"} records how extraction was produced.
    """
    errors: list[str] = []
    mode = "mock"

    # ── Step 1: Extraction ────────────────────────────────────────────────────
    try:
        # Get existing decisions for context (via MCP tool)
        existing_json = graph_get_all_decisions()

        # Use ExtractionAgentRunner (in-process, delegates to LangGraph or MockExtractor)
        from threadline.agents.extraction_agent import ExtractionAgentRunner
        from threadline.extractor import MockExtractor, _MOCK_RESPONSES
        from threadline.models import Decision

        # Routing (mirrors extractor.HybridExtractor + adds the Lyzr path):
        #   • the four canned demo fixtures ALWAYS use MockExtractor so the flagship
        #     supersession/conflict narrative stays deterministic, even with a key set;
        #   • otherwise prefer Lyzr Studio (mandatory integration) when configured;
        #   • else the in-process Gemini/OpenAI LangGraph runner;
        #   • else deterministic mock.
        is_fixture = meeting_id in _MOCK_RESPONSES
        has_llm_key = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY"))
        lyzr_ready = _lyzr_ready()

        extraction = None
        if is_fixture or not (has_llm_key or lyzr_ready):
            reason = "demo fixture — deterministic" if is_fixture else "no LLM key / Lyzr"
            logger.info("[%s] Using MockExtractor (%s)", correlation_id, reason)
            mock = MockExtractor()
            existing_decisions = [Decision.model_validate(d) for d in json.loads(existing_json)]
            transcript = MeetingTranscript(
                id=meeting_id,
                source_file=source_file,
                text=transcript_text,
                meeting_title=meeting_title,
            )
            extraction = mock.extract(transcript, existing_decisions)
            mode = "mock"
        else:
            if lyzr_ready:
                extraction = _lyzr_extract(
                    meeting_id=meeting_id,
                    transcript_text=transcript_text,
                    meeting_title=meeting_title,
                    existing_decisions_json=existing_json,
                    correlation_id=correlation_id,
                )
                if extraction is not None:
                    mode = "lyzr"
            if extraction is None:
                if has_llm_key:
                    runner = ExtractionAgentRunner()
                    result_json = runner.extract(
                        meeting_id=meeting_id,
                        transcript_text=transcript_text,
                        meeting_title=meeting_title,
                        existing_decisions_json=existing_json,
                    )
                    extraction = ExtractionResult.model_validate_json(result_json)
                    mode = "adk"
                else:
                    # Lyzr was configured but failed, and there is no LLM key to
                    # fall back to — use deterministic mock rather than error out.
                    logger.warning("[%s] Lyzr failed and no LLM key — using MockExtractor",
                                   correlation_id)
                    mock = MockExtractor()
                    existing_decisions = [Decision.model_validate(d) for d in json.loads(existing_json)]
                    transcript = MeetingTranscript(
                        id=meeting_id, source_file=source_file,
                        text=transcript_text, meeting_title=meeting_title,
                    )
                    extraction = mock.extract(transcript, existing_decisions)
                    mode = "mock"

        logger.info(
            "[%s] Extraction done via %s: %d decisions, %d action items",
            correlation_id, mode, len(extraction.decisions), len(extraction.action_items),
        )
    except Exception as exc:
        msg = f"Extraction failed: {exc}"
        logger.error("[%s] %s", correlation_id, msg)
        errors.append(msg)
        extraction = None

    # ── Step 2: Graph Write ───────────────────────────────────────────────────
    if extraction:
        try:
            from threadline.agents.graph_writer_agent import GraphWriterAgentRunner
            writer = GraphWriterAgentRunner()
            writer.write(
                meeting_id=meeting_id,
                source_file=source_file,
                transcript_text=transcript_text,
                extraction=extraction,
            )
            logger.info("[%s] Graph write complete", correlation_id)
        except Exception as exc:
            msg = f"Graph write failed: {exc}"
            logger.error("[%s] %s", correlation_id, msg)
            errors.append(msg)

    # ── Step 3: Vector Index ──────────────────────────────────────────────────
    if extraction and extraction.facts:
        try:
            from threadline.agents.semantic_memory_agent import SemanticMemoryAgentRunner
            indexer = SemanticMemoryAgentRunner()
            indexer.index(extraction)
            logger.info("[%s] Vector index complete", correlation_id)
        except Exception as exc:
            msg = f"Vector index failed: {exc}"
            logger.error("[%s] %s", correlation_id, msg)
            errors.append(msg)

    # ── Step 4: Briefing ──────────────────────────────────────────────────────
    try:
        from threadline.agents.briefing_agent import BriefingAgentRunner
        briefing_runner = BriefingAgentRunner()
        briefing = briefing_runner.generate_briefing()
        logger.info("[%s] Briefing generated", correlation_id)
    except Exception as exc:
        msg = f"Briefing failed: {exc}"
        logger.error("[%s] %s", correlation_id, msg)
        errors.append(msg)
        briefing = None

    return extraction, briefing, errors, mode


# ─────────────────────────────────────────────────────────────────────────────
# ManagerAgentRunner — the unified orchestrator
# ─────────────────────────────────────────────────────────────────────────────

class ManagerAgentRunner:
    """
    Unified meeting pipeline orchestrator.

    Tries Lyzr Studio first (if LYZR_API_KEY + LYZR_AGENT_ID are set).
    Falls back to in-process ADK orchestration automatically.
    Logs which mode executed so demo inspectors can verify.
    """

    def run_streaming(
        self,
        source: str,
        meeting_id: str,
        content: bytes | None = None,
    ) -> Generator[StageEvent, None, PipelineResult]:
        """
        Orchestrate the full pipeline, yielding StageEvents for SSE streaming.

        Same API contract as Pipeline.run_streaming() so the FastAPI endpoint
        doesn't need to change.
        """
        import pathlib
        source_path = pathlib.Path(source)
        correlation_id = str(uuid.uuid4())[:8]

        result = PipelineResult(meeting_id=meeting_id)

        def emit(stage: PipelineStage, status: StageStatus, msg: str,
                 data: dict | None = None) -> StageEvent:
            ev = StageEvent(stage=stage, status=status, message=msg, data=data or {})
            result.stage_events.append(ev)
            return ev

        logger.info("[%s] Manager: starting pipeline for %s", correlation_id, meeting_id)

        # ── 1. INGEST ─────────────────────────────────────────────────────────
        yield emit(PipelineStage.INGEST, StageStatus.running, "Reading source file…")
        try:
            from threadline.agents.input_agent import InputAgentRunner
            input_runner = InputAgentRunner(
                gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
                gemini_model=os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest"),
                openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
                gemini_model=os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest"),
            )
            transcript, is_audio = input_runner.ingest(source_path, meeting_id, content)
            yield emit(
                PipelineStage.INGEST, StageStatus.done,
                f"Loaded {len(transcript.text):,} characters",
                {"char_count": len(transcript.text), "is_audio": is_audio, "correlation_id": correlation_id},
            )
        except Exception as exc:
            msg = f"Ingest failed: {exc}"
            logger.exception("[%s] %s", correlation_id, msg)
            result.overall_success = False
            result.errors.append(msg)
            yield emit(PipelineStage.INGEST, StageStatus.error, msg)
            yield emit(PipelineStage.PIPELINE, StageStatus.error, "Aborted at INGEST",
                       {"meeting_id": meeting_id, "errors": result.errors})
            return result

        # ── 2. TRANSCRIBE (audio only) ────────────────────────────────────────
        if is_audio:
            yield emit(PipelineStage.TRANSCRIBE, StageStatus.running,
                       "Transcribing audio via Gemini…")
            try:
                transcript = input_runner.transcribe(transcript, source_path, content)
                yield emit(PipelineStage.TRANSCRIBE, StageStatus.done,
                           f"Transcribed: {len(transcript.text):,} characters",
                           {"correlation_id": correlation_id})
            except Exception as exc:
                msg = f"Transcription failed: {exc}"
                logger.error("[%s] %s", correlation_id, msg)
                result.overall_success = False
                result.errors.append(msg)
                yield emit(PipelineStage.TRANSCRIBE, StageStatus.error, msg)
                yield emit(PipelineStage.PIPELINE, StageStatus.error, "Aborted at TRANSCRIBE",
                           {"meeting_id": meeting_id, "errors": result.errors})
                return result
        else:
            yield emit(PipelineStage.TRANSCRIBE, StageStatus.skipped,
                       "Transcript input — transcription skipped")

        # ── 3. EXTRACT → GRAPH → VECTOR → BRIEFING ───────────────────────────
        # Extraction may be delegated to a Lyzr Studio agent (the mandatory Lyzr
        # integration); persistence to the local graph/vector stores always runs
        # in-process afterwards, since hosted Lyzr cannot write to our Neo4j/Qdrant.
        yield emit(PipelineStage.EXTRACT, StageStatus.running,
                   "Extracting facts (Manager delegating…)")

        extraction, briefing, errors, mode = _adk_orchestrate(
            meeting_id=meeting_id,
            source_file=str(source_path),
            transcript_text=transcript.text,
            meeting_title=transcript.meeting_title or meeting_id,
            correlation_id=correlation_id,
            content=content,
        )
        mode_label = {"lyzr": "Lyzr Studio", "adk": "Gemini/ADK",
                      "mock": "demo data"}.get(mode, mode)
        logger.info("[%s] Orchestrated extraction via %s", correlation_id, mode_label)

        if extraction:
            result.extraction_result = extraction
            nd = len(extraction.decisions)
            na = len(extraction.action_items)
            nc = len(extraction.new_conflicts)
            ns = len(extraction.supersessions)
            yield emit(PipelineStage.EXTRACT, StageStatus.done,
                       f"{nd} decisions, {na} action items, {nc} conflict(s), {ns} supersession(s)",
                       {"decisions": nd, "action_items": na,
                        "conflicts": nc, "supersessions": ns,
                        "mode": mode, "correlation_id": correlation_id})
        else:
            for err in errors:
                result.errors.append(err)
            yield emit(PipelineStage.EXTRACT, StageStatus.error,
                       "Extraction failed")

        # ── 4. GRAPH_WRITE ────────────────────────────────────────────────────
        if extraction and not any("Graph write" in e for e in errors):
            result.graph_success = True
            yield emit(PipelineStage.GRAPH_WRITE, StageStatus.done,
                       f"Graph updated ({mode_label})",
                       {"correlation_id": correlation_id})
        else:
            graph_errors = [e for e in errors if "Graph" in e]
            if graph_errors:
                yield emit(PipelineStage.GRAPH_WRITE, StageStatus.error,
                           graph_errors[-1])
            else:
                yield emit(PipelineStage.GRAPH_WRITE, StageStatus.skipped,
                           "Skipped — no extraction result")

        # ── 5. VECTOR_WRITE ───────────────────────────────────────────────────
        if extraction and extraction.facts and not any("Vector" in e for e in errors):
            result.vector_success = True
            yield emit(PipelineStage.VECTOR_WRITE, StageStatus.done,
                       f"Vector indexed ({mode_label})",
                       {"correlation_id": correlation_id})
        else:
            vec_errors = [e for e in errors if "Vector" in e]
            if vec_errors:
                yield emit(PipelineStage.VECTOR_WRITE, StageStatus.error,
                           vec_errors[-1])
            else:
                yield emit(PipelineStage.VECTOR_WRITE, StageStatus.skipped,
                           "Skipped — no facts")

        # ── 6. BRIEFING ───────────────────────────────────────────────────────
        if briefing:
            result.briefing_success = True
            yield emit(PipelineStage.BRIEFING, StageStatus.done,
                       f"Briefing generated ({mode_label})",
                       {"correlation_id": correlation_id})
        else:
            briefing_errors = [e for e in errors if "Briefing" in e]
            if briefing_errors:
                yield emit(PipelineStage.BRIEFING, StageStatus.error,
                           briefing_errors[-1])
            else:
                yield emit(PipelineStage.BRIEFING, StageStatus.skipped,
                           "Skipped")

        # Propagate errors to result
        for err in errors:
            if err not in result.errors:
                result.errors.append(err)

        # ── Final ─────────────────────────────────────────────────────────────
        final_status = StageStatus.done if not result.errors else StageStatus.error
        final_msg = (
            f"Pipeline complete [{mode}, corr={correlation_id}]"
            if not result.errors
            else f"Pipeline complete with {len(result.errors)} error(s)"
        )
        yield emit(PipelineStage.PIPELINE, final_status, final_msg, {
            "meeting_id": meeting_id,
            "graph_success": result.graph_success,
            "vector_success": result.vector_success,
            "briefing_success": result.briefing_success,
            "errors": result.errors,
            "correlation_id": correlation_id,
            "orchestrator": mode,
        })
        return result

    def run_sync(
        self,
        source: str,
        meeting_id: str,
        content: bytes | None = None,
    ) -> PipelineResult:
        """Drain run_streaming() synchronously."""
        gen = self.run_streaming(source, meeting_id, content)
        result = None
        try:
            while True:
                event = next(gen)
                logger.info("[Manager] %s %s — %s",
                            event.stage.value, event.status.value, event.message)
        except StopIteration as stop:
            result = stop.value
        return result or PipelineResult(
            meeting_id=str(meeting_id),
            overall_success=False,
            errors=["Manager agent generator returned no result"],
        )


# ─────────────────────────────────────────────────────────────────────────────
# ADK Agent creation (Manager as ADK Agent)
# ─────────────────────────────────────────────────────────────────────────────

def create_manager_adk_agent():
    """Create the Manager as a Google ADK Agent (A2A client)."""
    try:
        from google.adk.agents import Agent
        agent = Agent(
            name=AGENT_NAME,
            model="gemini-2.0-flash",
            description=AGENT_DESCRIPTION,
            instruction=(
                "You are the Tesseract Manager Agent. Coordinate the full meeting intelligence "
                "pipeline by delegating to specialized agents: Input → Extraction → Graph Writer "
                "→ Semantic Memory → Briefing. Prefer Lyzr Studio orchestration when available; "
                "fall back to ADK in-process runners automatically."
            ),
            tools=[],
        )
        logger.info("Created ADK Manager Agent: %s", AGENT_NAME)
        return agent
    except ImportError:
        logger.warning("google-adk not installed — Manager ADK agent unavailable")
        return None
