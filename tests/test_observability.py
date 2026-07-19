"""
Tests for Tesseract Phase 13 Lightweight Observability.
Verify that correlation IDs are correctly propagated and emitted at agent boundaries.
"""
from __future__ import annotations

import pytest
from threadline.extractor import MockExtractor
from threadline.models import MeetingTranscript
from threadline.agents.manager_agent import ManagerAgentRunner
from threadline.mcp.graph_mcp import set_graph_store
from threadline.mcp.vector_mcp import set_vector_store
from threadline.graph_store import InMemoryGraphStore
from threadline.vector_store import InMemoryVectorStore


def test_correlation_id_propagation():
    # 1. Initialize stores and register MCP singleton references
    gs = InMemoryGraphStore()
    set_graph_store(gs)
    
    vs = InMemoryVectorStore()
    vs._use_hash_embed = True
    set_vector_store(vs)

    # 2. Run the pipeline with streaming
    manager = ManagerAgentRunner()
    
    from pathlib import Path
    fixtures_dir = Path(__file__).parent / "fixtures"
    meeting_01_path = fixtures_dir / "meeting_01.txt"
    
    events_gen = manager.run_streaming(
        source=str(meeting_01_path),
        meeting_id="meeting_01"
    )
    
    events = list(events_gen)
    assert len(events) >= 5
    
    # Extract correlation ID from first event
    corr_ids = []
    for ev in events:
        data = ev.data or {}
        corr_id = data.get("correlation_id")
        if corr_id:
            corr_ids.append(corr_id)

    # Ensure we got correlation IDs propagated across multiple stages
    assert len(corr_ids) >= 3
    # Check that they are all the same correlation ID (propagation check)
    first_id = corr_ids[0]
    for cid in corr_ids:
        assert cid == first_id, f"Correlation ID changed during pipeline run: {cid} != {first_id}"
