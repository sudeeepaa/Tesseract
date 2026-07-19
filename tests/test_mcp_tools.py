"""
Tests for threadline/mcp/ tool wrappers.

Validates that MCP tool functions correctly delegate to the underlying
store implementations and produce valid JSON responses.
"""
from __future__ import annotations

import json

import pytest

from threadline.graph_store import InMemoryGraphStore
from threadline.vector_store import InMemoryVectorStore
from threadline.mcp.graph_mcp import (
    set_graph_store,
    graph_upsert_extraction,
    graph_get_all_decisions,
    graph_get_all_action_items,
    graph_get_all_conflicts,
    graph_get_all_topics,
    graph_get_meeting_count,
    graph_get_snapshot,
    graph_get_status,
    GRAPH_MCP_TOOLS,
)
from threadline.mcp.vector_mcp import (
    set_vector_store,
    vector_upsert_chunks,
    vector_search,
    vector_get_status,
    VECTOR_MCP_TOOLS,
)
from threadline.extractor import MockExtractor
from threadline.models import (
    Decision,
    DecisionStatus,
    ExtractionResult,
    ExtractedFact,
    FactType,
    MeetingTranscript,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_stores():
    """Set up fresh in-memory stores for each test."""
    gs = InMemoryGraphStore()
    set_graph_store(gs)

    vs = InMemoryVectorStore()
    vs._use_hash_embed = True  # fast hash fallback in tests
    set_vector_store(vs)

    yield gs, vs


@pytest.fixture
def mock_extractor():
    return MockExtractor()


# ─────────────────────────────────────────────────────────────────────────────
# Graph MCP Tools
# ─────────────────────────────────────────────────────────────────────────────

class TestGraphMCPTools:
    def test_tool_registry_has_all_tools(self):
        assert len(GRAPH_MCP_TOOLS) == 8
        names = [t.__name__ for t in GRAPH_MCP_TOOLS]
        assert "graph_upsert_extraction" in names
        assert "graph_get_all_decisions" in names
        assert "graph_get_all_conflicts" in names

    def test_all_tools_have_docstrings(self):
        for tool in GRAPH_MCP_TOOLS:
            assert tool.__doc__ is not None, f"{tool.__name__} missing docstring"

    def test_get_meeting_count_initially_zero(self):
        result = json.loads(graph_get_meeting_count())
        assert result["count"] == 0

    def test_get_all_decisions_initially_empty(self):
        result = json.loads(graph_get_all_decisions())
        assert result == []

    def test_upsert_and_read_decisions(self, mock_extractor):
        t = MeetingTranscript(id="meeting_01", source_file="m1.txt", text="test")
        extraction = mock_extractor.extract(t)

        stats_json = graph_upsert_extraction(
            meeting_id="meeting_01",
            source_file="m1.txt",
            transcript_text="test",
            extraction_json=extraction.model_dump_json(),
        )
        stats = json.loads(stats_json)
        assert stats["new_nodes"] >= 4

        decisions_json = graph_get_all_decisions()
        decisions = json.loads(decisions_json)
        assert len(decisions) >= 4
        texts = [d["text"] for d in decisions]
        assert any("React" in t for t in texts)

    def test_get_meeting_count_after_upsert(self, mock_extractor):
        t = MeetingTranscript(id="meeting_01", source_file="m1.txt", text="test")
        extraction = mock_extractor.extract(t)
        graph_upsert_extraction(
            meeting_id="meeting_01",
            source_file="m1.txt",
            transcript_text="test",
            extraction_json=extraction.model_dump_json(),
        )
        result = json.loads(graph_get_meeting_count())
        assert result["count"] == 1

    def test_get_all_action_items(self, mock_extractor):
        t = MeetingTranscript(id="meeting_01", source_file="m1.txt", text="test")
        extraction = mock_extractor.extract(t)
        graph_upsert_extraction(
            meeting_id="meeting_01",
            source_file="m1.txt",
            transcript_text="test",
            extraction_json=extraction.model_dump_json(),
        )
        items = json.loads(graph_get_all_action_items())
        assert len(items) >= 1

    def test_get_all_topics(self, mock_extractor):
        t = MeetingTranscript(id="meeting_01", source_file="m1.txt", text="test")
        extraction = mock_extractor.extract(t)
        graph_upsert_extraction(
            meeting_id="meeting_01",
            source_file="m1.txt",
            transcript_text="test",
            extraction_json=extraction.model_dump_json(),
        )
        topics = json.loads(graph_get_all_topics())
        assert len(topics) >= 1

    def test_get_snapshot_returns_valid_json(self, mock_extractor):
        t = MeetingTranscript(id="meeting_01", source_file="m1.txt", text="test")
        extraction = mock_extractor.extract(t)
        graph_upsert_extraction(
            meeting_id="meeting_01",
            source_file="m1.txt",
            transcript_text="test",
            extraction_json=extraction.model_dump_json(),
        )
        snapshot = json.loads(graph_get_snapshot())
        assert "nodes" in snapshot
        assert "edges" in snapshot
        assert len(snapshot["nodes"]) >= 5

    def test_get_status(self):
        status = json.loads(graph_get_status())
        assert status["connected"] is True
        assert status["backend"] == "memory"

    def test_conflicts_after_meeting_03(self, mock_extractor):
        """Verify conflict detection works through MCP tools."""
        # Process meetings 01, 02, 03
        for mid in ["meeting_01", "meeting_02", "meeting_03"]:
            t = MeetingTranscript(id=mid, source_file=f"{mid}.txt", text="test")
            existing = json.loads(graph_get_all_decisions())
            existing_decisions = [Decision.model_validate(d) for d in existing]
            extraction = mock_extractor.extract(t, existing_decisions)
            graph_upsert_extraction(
                meeting_id=mid,
                source_file=f"{mid}.txt",
                transcript_text="test",
                extraction_json=extraction.model_dump_json(),
            )

        conflicts = json.loads(graph_get_all_conflicts())
        open_conflicts = [c for c in conflicts if not c["resolved"]]
        assert len(open_conflicts) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Vector MCP Tools
# ─────────────────────────────────────────────────────────────────────────────

class TestVectorMCPTools:
    def test_tool_registry_has_all_tools(self):
        assert len(VECTOR_MCP_TOOLS) == 3
        names = [t.__name__ for t in VECTOR_MCP_TOOLS]
        assert "vector_upsert_chunks" in names
        assert "vector_search" in names
        assert "vector_get_status" in names

    def test_all_tools_have_docstrings(self):
        for tool in VECTOR_MCP_TOOLS:
            assert tool.__doc__ is not None, f"{tool.__name__} missing docstring"

    def test_upsert_and_search(self, mock_extractor):
        t = MeetingTranscript(id="meeting_01", source_file="m1.txt", text="test")
        extraction = mock_extractor.extract(t)

        result = json.loads(vector_upsert_chunks(extraction.model_dump_json()))
        assert result["chunks_indexed"] >= 1

        search_results = json.loads(vector_search("authentication provider"))
        assert len(search_results) >= 1
        # Results should have required fields
        assert "fact_id" in search_results[0]
        assert "text" in search_results[0]
        assert "score" in search_results[0]

    def test_get_status(self):
        status = json.loads(vector_get_status())
        assert status["connected"] is True
        assert status["backend"] == "memory"

    def test_search_empty_store(self):
        results = json.loads(vector_search("anything"))
        assert results == []

    def test_upsert_returns_correct_count(self):
        f1 = ExtractedFact(
            id="f1", claim_text="Use PostgreSQL",
            fact_type=FactType.decision, source_meeting_id="m1",
        )
        f2 = ExtractedFact(
            id="f2", claim_text="Assign Dev to write tests",
            fact_type=FactType.action_item, source_meeting_id="m1",
        )
        extraction = ExtractionResult(meeting_id="m1", facts=[f1, f2])
        result = json.loads(vector_upsert_chunks(extraction.model_dump_json()))
        assert result["chunks_indexed"] == 2
