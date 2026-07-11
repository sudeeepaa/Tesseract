"""
Tests for threadline/pipeline.py (and integration between all Day 1 components)

All tests use in-memory backends — no Docker required.
The end-to-end sequence test processes all 4 fixtures in order to verify
the full supersession + conflict + resolution story.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from threadline.models import (
    DecisionStatus,
    PipelineStage,
    StageStatus,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline.run_sync — basic smoke tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineRunSync:
    def test_returns_pipeline_result(self, pipeline):
        r = pipeline.run_sync(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        assert r.meeting_id == "meeting_01"

    def test_overall_success_true_for_clean_run(self, pipeline):
        r = pipeline.run_sync(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        assert r.overall_success is True
        assert r.errors == []

    def test_extraction_result_populated(self, pipeline):
        r = pipeline.run_sync(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        assert r.extraction_result is not None
        assert r.extraction_result.meeting_id == "meeting_01"

    def test_graph_success_true(self, pipeline):
        r = pipeline.run_sync(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        assert r.graph_success is True

    def test_vector_success_true(self, pipeline):
        r = pipeline.run_sync(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        assert r.vector_success is True

    def test_briefing_success_true(self, pipeline):
        r = pipeline.run_sync(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        assert r.briefing_success is True

    def test_missing_file_is_handled(self, pipeline):
        """A missing file should fail at INGEST, not crash the process."""
        r = pipeline.run_sync(Path("nonexistent_meeting.txt"), "bad_meeting")
        assert r.overall_success is False
        assert len(r.errors) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline.run_streaming — StageEvent sequence
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineStreamingEvents:
    def _drain(self, gen):
        events = []
        result = None
        try:
            while True:
                events.append(next(gen))
        except StopIteration as stop:
            result = stop.value
        return events, result

    def test_all_stages_emitted(self, pipeline):
        gen = pipeline.run_streaming(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        events, _ = self._drain(gen)
        stages = [e.stage for e in events]
        assert PipelineStage.INGEST      in stages
        assert PipelineStage.TRANSCRIBE  in stages
        assert PipelineStage.EXTRACT     in stages
        assert PipelineStage.GRAPH_WRITE in stages
        assert PipelineStage.VECTOR_WRITE in stages
        assert PipelineStage.BRIEFING    in stages
        assert PipelineStage.PIPELINE    in stages

    def test_transcribe_is_skipped_for_text(self, pipeline):
        gen = pipeline.run_streaming(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        events, _ = self._drain(gen)
        transcribe_events = [e for e in events if e.stage == PipelineStage.TRANSCRIBE]
        assert len(transcribe_events) >= 1
        assert any(e.status == StageStatus.skipped for e in transcribe_events)

    def test_final_pipeline_event_is_done(self, pipeline):
        gen = pipeline.run_streaming(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        events, _ = self._drain(gen)
        final = [e for e in events if e.stage == PipelineStage.PIPELINE][-1]
        assert final.status == StageStatus.done

    def test_result_returned_via_stop_iteration(self, pipeline):
        gen = pipeline.run_streaming(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        _, result = self._drain(gen)
        assert result is not None
        assert result.meeting_id == "meeting_01"


# ─────────────────────────────────────────────────────────────────────────────
# Graph store state after pipeline runs
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineGraphState:
    def test_decisions_stored_after_run(self, pipeline, graph_store):
        pipeline.run_sync(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        decisions = graph_store.get_all_decisions()
        assert len(decisions) >= 4

    def test_meeting_count_increments(self, pipeline, graph_store):
        pipeline.run_sync(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        assert graph_store.get_meeting_count() == 1
        pipeline.run_sync(FIXTURES_DIR / "meeting_02.txt", "meeting_02")
        assert graph_store.get_meeting_count() == 2

    def test_postgres_superseded_after_meeting_02(self, pipeline, graph_store):
        """After processing meetings 01 and 02, Postgres decision must be superseded."""
        pipeline.run_sync(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        pipeline.run_sync(FIXTURES_DIR / "meeting_02.txt", "meeting_02")

        all_decisions = graph_store.get_all_decisions()
        postgres_decisions = [d for d in all_decisions if "PostgreSQL" in d.text]
        assert len(postgres_decisions) >= 1
        pg_d = postgres_decisions[0]
        assert pg_d.status == DecisionStatus.superseded, (
            f"PostgreSQL decision should be superseded after meeting_02, "
            f"got '{pg_d.status.value}'"
        )

    def test_auth0_under_review_after_meeting_03(self, pipeline, graph_store):
        """
        After meetings 01, 02, 03:
        Auth0 must be under_review — not superseded.
        """
        pipeline.run_sync(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        pipeline.run_sync(FIXTURES_DIR / "meeting_02.txt", "meeting_02")
        pipeline.run_sync(FIXTURES_DIR / "meeting_03.txt", "meeting_03")

        all_decisions = graph_store.get_all_decisions()
        auth0_decisions = [d for d in all_decisions if "Auth0" in d.text]
        assert len(auth0_decisions) >= 1
        auth0 = auth0_decisions[0]
        assert auth0.status == DecisionStatus.under_review, (
            f"Auth0 should be 'under_review' after meeting_03 (concern raised, "
            f"no replacement chosen yet). Got '{auth0.status.value}'."
        )
        assert auth0.status != DecisionStatus.superseded, (
            "Auth0 must NOT be superseded after meeting_03 — "
            "Keycloak is not confirmed until meeting_04."
        )

    def test_auth0_superseded_after_meeting_04(self, pipeline, graph_store):
        """After meeting_04, Auth0 is superseded by Keycloak."""
        for meeting in ["meeting_01", "meeting_02", "meeting_03", "meeting_04"]:
            pipeline.run_sync(FIXTURES_DIR / f"{meeting}.txt", meeting)

        all_decisions = graph_store.get_all_decisions()
        auth0_decisions = [d for d in all_decisions if "Auth0" in d.text]
        assert len(auth0_decisions) >= 1
        auth0 = auth0_decisions[0]
        assert auth0.status == DecisionStatus.superseded

    def test_conflict_open_after_meeting_03(self, pipeline, graph_store):
        pipeline.run_sync(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        pipeline.run_sync(FIXTURES_DIR / "meeting_02.txt", "meeting_02")
        pipeline.run_sync(FIXTURES_DIR / "meeting_03.txt", "meeting_03")

        conflicts = graph_store.get_all_conflicts()
        open_conflicts = [c for c in conflicts if not c.resolved]
        assert len(open_conflicts) >= 1

    def test_conflict_resolved_after_meeting_04(self, pipeline, graph_store):
        for meeting in ["meeting_01", "meeting_02", "meeting_03", "meeting_04"]:
            pipeline.run_sync(FIXTURES_DIR / f"{meeting}.txt", meeting)

        conflicts = graph_store.get_all_conflicts()
        resolved = [c for c in conflicts if c.resolved]
        assert len(resolved) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Vector store state
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineVectorState:
    def test_facts_indexed_after_run(self, pipeline, vector_store):
        pipeline.run_sync(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        results = vector_store.search("authentication provider", top_k=5)
        assert len(results) >= 1

    def test_search_returns_ranked_results(self, pipeline, vector_store):
        pipeline.run_sync(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        results = vector_store.search("React frontend", top_k=3)
        assert len(results) <= 3
        # Results should be ordered by score descending
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# Graceful degradation
# ─────────────────────────────────────────────────────────────────────────────

class TestGracefulDegradation:
    def test_graph_store_failure_does_not_crash(self, mock_extractor, vector_store, briefing_gen):
        """If GraphStore raises on write, pipeline continues without crashing."""
        from threadline.graph_store import GraphStore
        from threadline.models import MeetingTranscript, GraphSnapshot
        from typing import Any

        class FailingGraphStore:
            def upsert_result(self, transcript, result) -> dict:
                raise RuntimeError("Simulated Neo4j connection failure")
            def get_all_decisions(self):      return []
            def get_all_action_items(self):   return []
            def get_all_conflicts(self):      return []
            def get_all_topics(self):         return []
            def get_meeting_count(self):      return 0
            def get_graph_snapshot(self):     return GraphSnapshot()
            def get_status(self):             return {"connected": False, "backend": "memory"}

        from threadline.pipeline import Pipeline
        p = Pipeline(
            extractor=mock_extractor,
            graph_store=FailingGraphStore(),
            vector_store=vector_store,
            briefing_gen=briefing_gen,
        )
        result = p.run_sync(FIXTURES_DIR / "meeting_01.txt", "meeting_01")

        # Must not raise; errors are captured
        assert result.graph_success is False
        assert any("Simulated" in e or "Graph" in e for e in result.errors)
        # But briefing should still succeed (using empty store data)
        assert result.briefing_success is True

    def test_vector_store_failure_does_not_crash(self, mock_extractor, graph_store, briefing_gen):
        """If VectorStore raises on write, pipeline continues."""
        from threadline.models import SearchResult

        class FailingVectorStore:
            def upsert_chunks(self, result) -> int:
                raise RuntimeError("Simulated Qdrant connection failure")
            def search(self, query, top_k=5): return []
            def get_status(self): return {"connected": False, "backend": "memory"}

        from threadline.pipeline import Pipeline
        p = Pipeline(
            extractor=mock_extractor,
            graph_store=graph_store,
            vector_store=FailingVectorStore(),
            briefing_gen=briefing_gen,
        )
        result = p.run_sync(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        assert result.vector_success is False
        assert result.graph_success  is True   # graph still worked
        assert result.briefing_success is True


# ─────────────────────────────────────────────────────────────────────────────
# Briefing content
# ─────────────────────────────────────────────────────────────────────────────

class TestBriefingContent:
    def test_briefing_markdown_not_empty(self, pipeline):
        pipeline.run_sync(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        briefing_output = pipeline.briefing_gen.generate(
            all_decisions=pipeline.graph_store.get_all_decisions(),
            all_action_items=pipeline.graph_store.get_all_action_items(),
            all_conflicts=pipeline.graph_store.get_all_conflicts(),
            all_topics=pipeline.graph_store.get_all_topics(),
            meeting_count=pipeline.graph_store.get_meeting_count(),
        )
        assert len(briefing_output.markdown) > 100
        assert "Threadline" in briefing_output.markdown

    def test_under_review_section_appears_after_meeting_03(self, pipeline):
        """The briefing must have a separate '⚠️ Decisions Under Review' section
        after meeting_03 — not a 'superseded' section."""
        for m in ["meeting_01", "meeting_02", "meeting_03"]:
            pipeline.run_sync(FIXTURES_DIR / f"{m}.txt", m)

        briefing = pipeline.briefing_gen.generate(
            all_decisions=pipeline.graph_store.get_all_decisions(),
            all_action_items=pipeline.graph_store.get_all_action_items(),
            all_conflicts=pipeline.graph_store.get_all_conflicts(),
            all_topics=pipeline.graph_store.get_all_topics(),
            meeting_count=pipeline.graph_store.get_meeting_count(),
        )
        assert "Under Review" in briefing.markdown, (
            "Briefing must show Auth0 under the 'Under Review' section after meeting_03"
        )

    def test_graph_snapshot_has_supersedes_edge_after_meeting_02(self, pipeline):
        pipeline.run_sync(FIXTURES_DIR / "meeting_01.txt", "meeting_01")
        pipeline.run_sync(FIXTURES_DIR / "meeting_02.txt", "meeting_02")
        snap = pipeline.graph_store.get_graph_snapshot()
        from threadline.models import EdgeType
        supersedes_edges = [e for e in snap.edges if e.type == EdgeType.supersedes]
        assert len(supersedes_edges) >= 1, (
            "Graph snapshot must contain at least one SUPERSEDES edge after meeting_02"
        )
        assert all(e.superseded for e in supersedes_edges), (
            "All SUPERSEDES edges should have superseded=True for frontend styling"
        )
