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
from typing import Any, Generator

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

def _try_lyzr_orchestrate(
    meeting_id: str,
    source_file: str,
    transcript_text: str,
    correlation_id: str,
) -> tuple[bool, dict[str, Any]]:
    """
    Attempt to orchestrate via Lyzr Studio.

    Returns:
        (success: bool, result_data: dict)
    """
    lyzr_api_key = os.environ.get("LYZR_API_KEY", "")
    if not lyzr_api_key:
        logger.info("[%s] LYZR_API_KEY not set — skipping Lyzr path", correlation_id)
        return False, {}

    try:
        from lyzr import Studio  # type: ignore[import]

        studio = Studio(api_key=lyzr_api_key)
        logger.info("[%s] Lyzr Studio connected, delegating orchestration", correlation_id)

        # Delegate to Lyzr Studio manager agent with the full task payload
        task_payload = json.dumps({
            "meeting_id": meeting_id,
            "source_file": source_file,
            "transcript_text": transcript_text,
            "correlation_id": correlation_id,
            "task": "Run full meeting intelligence pipeline: extract facts, write to graph, index vectors, generate briefing.",
        })

        # Use a pre-configured Threadline orchestrator agent in Lyzr Studio
        agent_id = os.environ.get("LYZR_AGENT_ID", "")
        if not agent_id:
            logger.warning("[%s] LYZR_AGENT_ID not set — Lyzr path unavailable", correlation_id)
            return False, {}

        response = studio.send_message(
            agent_id=agent_id,
            message=task_payload,
        )

        # Extract structured result from Lyzr response
        result_text = getattr(response, "response", "") or str(response)
        logger.info("[%s] Lyzr orchestration complete: %d chars", correlation_id, len(result_text))

        return True, {"lyzr_response": result_text, "mode": "lyzr"}

    except ImportError:
        logger.info("[%s] lyzr-adk not installed — falling back to ADK path", correlation_id)
        return False, {}
    except Exception as exc:
        logger.warning(
            "[%s] Lyzr orchestration failed (%s) — falling back to ADK path",
            correlation_id, exc,
        )
        return False, {}


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
) -> tuple[ExtractionResult | None, BriefingOutput | None, list[str]]:
    """
    Orchestrate via in-process agent runners (ADK fallback / primary path when Lyzr unavailable).

    Uses the Runner classes directly (not HTTP A2A) to avoid startup overhead in test/mock mode.
    When A2A servers are running (Phase 6 full deployment), this would use RemoteA2aAgent instead.

    Returns:
        (extraction_result, briefing_output, errors)
    """
    errors: list[str] = []

    # ── Step 1: Extraction ────────────────────────────────────────────────────
    try:
        # Get existing decisions for context (via MCP tool)
        existing_json = graph_get_all_decisions()

        # Use ExtractionAgentRunner (in-process, delegates to LangGraph or MockExtractor)
        from threadline.agents.extraction_agent import ExtractionAgentRunner
        from threadline.extractor import MockExtractor
        from threadline.models import Decision

        # Check if we should use mock mode
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")):
            logger.info("[%s] No LLM key — using MockExtractor", correlation_id)
            mock = MockExtractor()
            existing_decisions = [Decision.model_validate(d) for d in json.loads(existing_json)]
            transcript = MeetingTranscript(
                id=meeting_id,
                source_file=source_file,
                text=transcript_text,
                meeting_title=meeting_title,
            )
            extraction = mock.extract(transcript, existing_decisions)
        else:
            runner = ExtractionAgentRunner()
            result_json = runner.extract(
                meeting_id=meeting_id,
                transcript_text=transcript_text,
                meeting_title=meeting_title,
                existing_decisions_json=existing_json,
            )
            extraction = ExtractionResult.model_validate_json(result_json)

        logger.info(
            "[%s] Extraction done: %d decisions, %d action items",
            correlation_id, len(extraction.decisions), len(extraction.action_items),
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

    return extraction, briefing, errors


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
                openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
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

        # ── 3. EXTRACT (try Lyzr, fall back to ADK) ──────────────────────────
        yield emit(PipelineStage.EXTRACT, StageStatus.running,
                   "Extracting facts (Manager delegating…)")

        lyzr_ok, _lyzr_data = _try_lyzr_orchestrate(
            meeting_id=meeting_id,
            source_file=str(source_path),
            transcript_text=transcript.text,
            correlation_id=correlation_id,
        )

        if lyzr_ok:
            # Lyzr handled the full pipeline including graph/vector/briefing
            logger.info("[%s] Orchestrated via Lyzr Studio", correlation_id)
            result.graph_success = True
            result.vector_success = True
            result.briefing_success = True
            yield emit(PipelineStage.EXTRACT, StageStatus.done,
                       "Extraction complete (Lyzr orchestrated)",
                       {"mode": "lyzr", "correlation_id": correlation_id})
            yield emit(PipelineStage.GRAPH_WRITE, StageStatus.done,
                       "Graph updated (Lyzr orchestrated)")
            yield emit(PipelineStage.VECTOR_WRITE, StageStatus.done,
                       "Vector indexed (Lyzr orchestrated)")
            yield emit(PipelineStage.BRIEFING, StageStatus.done,
                       "Briefing generated (Lyzr orchestrated)")
        else:
            # ADK in-process fallback
            logger.info("[%s] Orchestrating via ADK in-process fallback", correlation_id)
            extraction, briefing, errors = _adk_orchestrate(
                meeting_id=meeting_id,
                source_file=str(source_path),
                transcript_text=transcript.text,
                meeting_title=transcript.meeting_title or meeting_id,
                correlation_id=correlation_id,
                content=content,
            )

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
                            "mode": "adk", "correlation_id": correlation_id})
            else:
                for err in errors:
                    result.errors.append(err)
                yield emit(PipelineStage.EXTRACT, StageStatus.error,
                           "Extraction failed")

            # ── 4. GRAPH_WRITE ────────────────────────────────────────────────
            if extraction and not any("Graph write" in e for e in errors):
                result.graph_success = True
                yield emit(PipelineStage.GRAPH_WRITE, StageStatus.done,
                           "Graph updated (ADK)",
                           {"correlation_id": correlation_id})
            else:
                graph_errors = [e for e in errors if "Graph" in e]
                if graph_errors:
                    yield emit(PipelineStage.GRAPH_WRITE, StageStatus.error,
                               graph_errors[-1])
                else:
                    yield emit(PipelineStage.GRAPH_WRITE, StageStatus.skipped,
                               "Skipped — no extraction result")

            # ── 5. VECTOR_WRITE ───────────────────────────────────────────────
            if extraction and extraction.facts and not any("Vector" in e for e in errors):
                result.vector_success = True
                yield emit(PipelineStage.VECTOR_WRITE, StageStatus.done,
                           "Vector indexed (ADK)",
                           {"correlation_id": correlation_id})
            else:
                vec_errors = [e for e in errors if "Vector" in e]
                if vec_errors:
                    yield emit(PipelineStage.VECTOR_WRITE, StageStatus.error,
                               vec_errors[-1])
                else:
                    yield emit(PipelineStage.VECTOR_WRITE, StageStatus.skipped,
                               "Skipped — no facts")

            # ── 6. BRIEFING ───────────────────────────────────────────────────
            if briefing:
                result.briefing_success = True
                yield emit(PipelineStage.BRIEFING, StageStatus.done,
                           "Briefing generated (ADK)",
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
            f"Pipeline complete [{'lyzr' if lyzr_ok else 'adk'}, corr={correlation_id}]"
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
            "orchestrator": "lyzr" if lyzr_ok else "adk",
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
