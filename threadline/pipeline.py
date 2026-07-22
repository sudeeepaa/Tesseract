"""
Threadline pipeline orchestrator.

Pipeline.run_streaming()  →  Generator[StageEvent, None, PipelineResult]
    Yields one StageEvent per stage transition.
    The FastAPI SSE endpoint consumes this generator directly.
    Each stage is independently error-handled; a failure in one stage
    never aborts subsequent stages (except INGEST failure, which has no
    data to pass forward).

Pipeline.run_sync()  →  PipelineResult
    Drains run_streaming() and returns the final PipelineResult.
    Used by the CLI developer tool.

create_pipeline(settings)  →  Pipeline
    Factory that wires up the correct Extractor / GraphStore / VectorStore
    based on config.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator

from threadline.briefing import BriefingGenerator
from threadline.models import (
    MeetingTranscript,
    PipelineResult,
    PipelineStage,
    StageEvent,
    StageStatus,
)

if TYPE_CHECKING:
    from threadline.extractor import Extractor
    from threadline.graph_store import GraphStore
    from threadline.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Audio file extensions that trigger the Whisper API transcription stage
_AUDIO_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".wav", ".ogg", ".flac", ".webm"}


class Pipeline:
    """
    Orchestrates the full processing pipeline for a single meeting file.

    Dependency-injection constructor: all stores and the extractor are
    passed in, making the pipeline trivially testable with in-memory stubs.
    """

    def __init__(
        self,
        extractor:       "Extractor",
        graph_store:     "GraphStore",
        vector_store:    "VectorStore",
        briefing_gen:    BriefingGenerator | None = None,
        openai_api_key:  str = "",
    ) -> None:
        self.extractor      = extractor
        self.graph_store    = graph_store
        self.vector_store   = vector_store
        self.briefing_gen   = briefing_gen or BriefingGenerator()
        self.openai_api_key = openai_api_key

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def run_streaming(
        self,
        source:     str | Path,
        meeting_id: str | None = None,
        content:    bytes | None = None,
    ) -> Generator[StageEvent, None, PipelineResult]:
        """
        Yields StageEvent objects as each pipeline stage begins / completes.

        Usage (sync):
            gen = pipeline.run_streaming("meeting.txt")
            try:
                while True:
                    event = next(gen)
            except StopIteration as stop:
                result = stop.value

        Usage (FastAPI async):
            async for chunk in _sse_generator(pipeline, source):
                yield chunk
        """
        source = Path(source) if isinstance(source, str) else source
        if meeting_id is None:
            meeting_id = source.stem

        result        = PipelineResult(meeting_id=meeting_id)
        extraction    = None
        briefing      = None

        def emit(stage: PipelineStage, status: StageStatus, msg: str,
                 data: dict[str, Any] | None = None) -> StageEvent:
            ev = StageEvent(stage=stage, status=status, message=msg, data=data)
            result.stage_events.append(ev)
            return ev

        # ── 1. INGEST ─────────────────────────────────────────────────────────
        yield emit(PipelineStage.INGEST, StageStatus.running, "Reading source file…")
        try:
            transcript, is_audio = self._ingest(source, meeting_id, content)
            yield emit(PipelineStage.INGEST, StageStatus.done,
                       f"Loaded {len(transcript.text):,} characters",
                       {"char_count": len(transcript.text), "is_audio": is_audio})
        except Exception as exc:
            msg = f"Ingest failed: {exc}"
            logger.exception(msg)
            result.overall_success = False
            result.errors.append(msg)
            yield emit(PipelineStage.INGEST,    StageStatus.error, msg)
            yield emit(PipelineStage.PIPELINE,  StageStatus.error, "Aborted at INGEST",
                       {"meeting_id": meeting_id, "errors": result.errors})
            return result

        # ── 2. TRANSCRIBE (audio only) ────────────────────────────────────────
        if is_audio:
            yield emit(PipelineStage.TRANSCRIBE, StageStatus.running,
                       "Transcribing audio via OpenAI Whisper API…")
            try:
                transcript = self._transcribe(transcript, source, content)
                yield emit(PipelineStage.TRANSCRIBE, StageStatus.done,
                           f"Transcribed: {len(transcript.text):,} characters")
            except Exception as exc:
                msg = f"Transcription failed: {exc}"
                logger.error(msg)
                result.overall_success = False
                result.errors.append(msg)
                yield emit(PipelineStage.TRANSCRIBE, StageStatus.error, msg)
                yield emit(PipelineStage.PIPELINE,   StageStatus.error, "Aborted at TRANSCRIBE",
                           {"meeting_id": meeting_id, "errors": result.errors})
                return result
        else:
            yield emit(PipelineStage.TRANSCRIBE, StageStatus.skipped,
                       "Transcript input — transcription skipped")

        # ── 3. EXTRACT ────────────────────────────────────────────────────────
        yield emit(PipelineStage.EXTRACT, StageStatus.running, "Extracting facts with LLM…")
        try:
            existing_decisions = self.graph_store.get_all_decisions()
        except Exception as exc:
            logger.warning("Could not fetch existing decisions for context: %s", exc)
            existing_decisions = []

        try:
            extraction         = self.extractor.extract(transcript, existing_decisions)
            result.extraction_result = extraction
            nd = len(extraction.decisions)
            na = len(extraction.action_items)
            nc = len(extraction.new_conflicts)
            ns = len(extraction.supersessions)
            yield emit(PipelineStage.EXTRACT, StageStatus.done,
                       f"{nd} decisions, {na} action items, {nc} conflict(s), {ns} supersession(s)",
                       {"decisions": nd, "action_items": na,
                        "conflicts": nc, "supersessions": ns})
            if extraction.extraction_errors:
                for err in extraction.extraction_errors:
                    logger.warning("Extraction warning: %s", err)
        except Exception as exc:
            msg = f"Extraction failed: {exc}"
            logger.error(msg)
            result.errors.append(msg)
            yield emit(PipelineStage.EXTRACT, StageStatus.error, msg)
            # Do NOT abort — continue to graph/vector/briefing with empty extraction

        # ── 4. GRAPH_WRITE ────────────────────────────────────────────────────
        yield emit(PipelineStage.GRAPH_WRITE, StageStatus.running,
                   "Updating knowledge graph…")
        if extraction:
            try:
                stats = self.graph_store.upsert_result(transcript, extraction)
                result.graph_success = True
                yield emit(PipelineStage.GRAPH_WRITE, StageStatus.done,
                           stats.get("summary", "Graph updated"), stats)
            except Exception as exc:
                msg = f"Graph write failed (degrading): {exc}"
                logger.error(msg)
                result.errors.append(msg)
                yield emit(PipelineStage.GRAPH_WRITE, StageStatus.error, msg)
        else:
            yield emit(PipelineStage.GRAPH_WRITE, StageStatus.skipped,
                       "Skipped — no extraction result available")

        # ── 5. VECTOR_WRITE ───────────────────────────────────────────────────
        yield emit(PipelineStage.VECTOR_WRITE, StageStatus.running,
                   "Indexing semantic embeddings…")
        if extraction and extraction.facts:
            try:
                n_chunks = self.vector_store.upsert_chunks(extraction)
                result.vector_success = True
                yield emit(PipelineStage.VECTOR_WRITE, StageStatus.done,
                           f"{n_chunks} chunk(s) indexed",
                           {"chunks_indexed": n_chunks})
            except Exception as exc:
                msg = f"Vector write failed (degrading): {exc}"
                logger.error(msg)
                result.errors.append(msg)
                yield emit(PipelineStage.VECTOR_WRITE, StageStatus.error, msg)
        else:
            yield emit(PipelineStage.VECTOR_WRITE, StageStatus.skipped,
                       "Skipped — no facts to index")

        # ── 6. BRIEFING ───────────────────────────────────────────────────────
        yield emit(PipelineStage.BRIEFING, StageStatus.running,
                   "Generating executive briefing…")
        try:
            all_decisions    = self.graph_store.get_all_decisions()
            all_actions      = self.graph_store.get_all_action_items()
            all_conflicts    = self.graph_store.get_all_conflicts()
            all_topics       = self.graph_store.get_all_topics()
            meeting_count    = self.graph_store.get_meeting_count()

            briefing = self.briefing_gen.generate(
                all_decisions=all_decisions,
                all_action_items=all_actions,
                all_conflicts=all_conflicts,
                all_topics=all_topics,
                meeting_count=meeting_count,
            )
            result.briefing_success = True
            yield emit(PipelineStage.BRIEFING, StageStatus.done,
                       "Briefing updated",
                       {"total_decisions": len(all_decisions),
                        "total_conflicts": len(all_conflicts),
                        "meeting_count": meeting_count})
        except Exception as exc:
            msg = f"Briefing generation failed (degrading): {exc}"
            logger.error(msg)
            result.errors.append(msg)
            yield emit(PipelineStage.BRIEFING, StageStatus.error, msg)

        # ── Final ─────────────────────────────────────────────────────────────
        final_status = StageStatus.done if not result.errors else StageStatus.error
        final_msg    = (
            "Pipeline complete"
            if not result.errors
            else f"Pipeline complete with {len(result.errors)} error(s)"
        )
        summary: dict[str, Any] = {
            "meeting_id":       meeting_id,
            "graph_success":    result.graph_success,
            "vector_success":   result.vector_success,
            "briefing_success": result.briefing_success,
            "errors":           result.errors,
        }
        if briefing:
            summary["total_decisions"] = len(briefing.decisions)
            summary["total_conflicts"] = len(briefing.conflicts)

        yield emit(PipelineStage.PIPELINE, final_status, final_msg, summary)
        return result

    def run_sync(
        self,
        source:     str | Path,
        meeting_id: str | None = None,
        content:    bytes | None = None,
    ) -> PipelineResult:
        """
        Drains run_streaming() synchronously and returns the PipelineResult.
        Used by the CLI; the FastAPI endpoint uses run_streaming() directly.
        """
        gen = self.run_streaming(source, meeting_id, content)
        result = None
        try:
            while True:
                event = next(gen)
                logger.info("[%s] %s — %s", event.stage.value, event.status.value, event.message)
        except StopIteration as stop:
            result = stop.value
        return result or PipelineResult(
            meeting_id=str(meeting_id or source),
            overall_success=False,
            errors=["Pipeline generator returned no result"],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _ingest(
        self,
        source:     Path,
        meeting_id: str,
        content:    bytes | None,
    ) -> tuple[MeetingTranscript, bool]:
        """
        Read the source and return (MeetingTranscript, is_audio).
        If `content` is provided (e.g. from FastAPI UploadFile.read()),
        it is used directly instead of reading from disk.
        """
        is_audio = source.suffix.lower() in _AUDIO_EXTENSIONS

        if is_audio:
            # Text is a placeholder; _transcribe() fills it in
            return MeetingTranscript(
                id=meeting_id,
                source_file=str(source),
                text="[AUDIO — pending transcription]",
                meeting_title=source.stem.replace("_", " ").title(),
            ), True

        if content is not None:
            text = content.decode("utf-8", errors="replace")
        else:
            text = source.read_text(encoding="utf-8", errors="replace")

        return MeetingTranscript(
            id=meeting_id,
            source_file=str(source),
            text=text,
            meeting_title=source.stem.replace("_", " ").title(),
        ), False

    def _transcribe(
        self,
        transcript: MeetingTranscript,
        source:     Path,
        content:    bytes | None = None,
    ) -> MeetingTranscript:
        """
        Call the OpenAI Whisper API to transcribe audio.
        Raises RuntimeError (with a helpful message) if no API key is set.
        """
        if not self.openai_api_key:
            raise RuntimeError(
                "Audio transcription requires OPENAI_API_KEY to be set. "
                "Upload a .txt transcript file instead, or set OPENAI_API_KEY in .env."
            )
        import io
        from openai import OpenAI
        client = OpenAI(api_key=self.openai_api_key)

        if content is not None:
            audio_file = io.BytesIO(content)
            audio_file.name = source.name   # Whisper API checks the file extension
            response = client.audio.transcriptions.create(
                model="whisper-1", file=audio_file, response_format="text"
            )
        else:
            with open(source, "rb") as f:
                response = client.audio.transcriptions.create(
                    model="whisper-1", file=f, response_format="text"
                )
        return transcript.model_copy(update={"text": str(response)})


# ─────────────────────────────────────────────────────────────────────────────
# AgentPipeline — Manager-Agent-backed wrapper (Phases 6+)
# ─────────────────────────────────────────────────────────────────────────────

class AgentPipeline:
    """
    Drop-in replacement for Pipeline that delegates all orchestration
    to ManagerAgentRunner (Lyzr Studio primary, ADK in-process fallback).

    Exposes exactly the same run_streaming() / run_sync() API as Pipeline
    so the FastAPI endpoint and demo.py need zero changes.

    This class is used by the FastAPI backend (via create_pipeline_agent()).
    The original Pipeline class is still used by tests via direct DI.
    """

    def __init__(self, graph_store, vector_store) -> None:
        # Wire MCP singleton stores so all agent MCP tools work
        from threadline.agents.agent_registry import wire_stores
        wire_stores(graph_store, vector_store)

        from threadline.agents.manager_agent import ManagerAgentRunner
        self._manager = ManagerAgentRunner()

        # Expose stores on self so FastAPI deps (get_graph_store, etc.) still work
        self.graph_store = graph_store
        self.vector_store = vector_store

    def run_streaming(
        self,
        source: str | Path,
        meeting_id: str | None = None,
        content: bytes | None = None,
    ) -> Generator[StageEvent, None, PipelineResult]:
        """Delegate to ManagerAgentRunner, then cache a per-meeting summary."""
        source = Path(source) if isinstance(source, str) else source
        if meeting_id is None:
            meeting_id = source.stem
        result = yield from self._manager.run_streaming(str(source), meeting_id, content)
        self._cache_meeting_summary(meeting_id, result)
        return result

    def run_sync(
        self,
        source: str | Path,
        meeting_id: str | None = None,
        content: bytes | None = None,
    ) -> PipelineResult:
        """Drain run_streaming() synchronously (so the summary is cached too)."""
        gen = self.run_streaming(source, meeting_id, content)
        result: PipelineResult | None = None
        try:
            while True:
                next(gen)
        except StopIteration as stop:
            result = stop.value
        return result or PipelineResult(meeting_id=str(meeting_id or source), overall_success=False)

    def _cache_meeting_summary(self, meeting_id: str, result) -> None:
        """
        Generate the meeting summary ONCE at ingestion and store it on the meeting,
        so the /meetings summary endpoint serves it without re-calling the LLM.
        Best-effort: any failure is logged and skipped (never breaks ingestion).
        """
        extraction = getattr(result, "extraction_result", None)
        if not extraction or not getattr(result, "graph_success", False):
            return
        try:
            from threadline.config import get_settings
            from threadline.summarizer import summarize_meeting

            meetings = {m.id: m for m in self.graph_store.get_all_meetings()}
            title = meetings[meeting_id].title if meeting_id in meetings else meeting_id
            topics = [t.name for t in getattr(extraction, "topics", [])]
            summary = summarize_meeting(
                title, extraction.decisions, extraction.action_items, topics, get_settings()
            )
            self.graph_store.set_meeting_summary(meeting_id, summary)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not cache meeting summary for %s: %s", meeting_id, exc)


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

def create_pipeline(settings=None) -> Pipeline:
    """
    Wires up a fully configured Pipeline from settings.
    Used by tests (direct DI with in-memory stores) and CLI.
    """
    if settings is None:
        from threadline.config import get_settings
        settings = get_settings()

    from threadline.extractor    import create_extractor
    from threadline.graph_store  import create_graph_store
    from threadline.vector_store import create_vector_store

    return Pipeline(
        extractor=create_extractor(settings),
        graph_store=create_graph_store(settings),
        vector_store=create_vector_store(settings),
        briefing_gen=BriefingGenerator(),
        openai_api_key=settings.openai_api_key,
    )


def create_pipeline_agent(settings=None) -> AgentPipeline:
    """
    Wires up an AgentPipeline backed by ManagerAgentRunner.
    Used by the FastAPI backend so all requests flow through the
    Lyzr + ADK agent orchestration system.
    """
    if settings is None:
        from threadline.config import get_settings
        settings = get_settings()

    from threadline.graph_store  import create_graph_store
    from threadline.vector_store import create_vector_store

    graph_store  = create_graph_store(settings)
    vector_store = create_vector_store(settings)

    return AgentPipeline(
        graph_store=graph_store,
        vector_store=vector_store,
    )
