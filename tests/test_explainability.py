"""
Tests for Tesseract Phase 8 Explainability Layer.
Verify every contradiction and stale-item flag carries confidence score and reasoning trace.
"""
from __future__ import annotations

import pytest
from threadline.extractor import MockExtractor
from threadline.models import MeetingTranscript, ActionItemStatus
from threadline.agents.briefing_agent import BriefingAgentRunner
from threadline.agents.manager_agent import ManagerAgentRunner
from threadline.mcp.graph_mcp import set_graph_store, graph_get_all_conflicts
from threadline.mcp.vector_mcp import set_vector_store
from threadline.graph_store import InMemoryGraphStore
from threadline.vector_store import InMemoryVectorStore


def test_conflict_and_staleness_explainability():
    # 1. Initialize stores and register MCP singleton references
    gs = InMemoryGraphStore()
    set_graph_store(gs)
    
    vs = InMemoryVectorStore()
    vs._use_hash_embed = True
    set_vector_store(vs)

    # 2. Run the 4 meetings sequence through the ManagerAgentRunner (ADK in-process mode)
    manager = ManagerAgentRunner()
    
    from pathlib import Path
    fixtures_dir = Path(__file__).parent / "fixtures"
    
    for i in range(1, 5):
        meeting_id = f"meeting_0{i}"
        file_path = fixtures_dir / f"{meeting_id}.txt"
        
        # Run sync pipeline
        result = manager.run_sync(
            source=str(file_path),
            meeting_id=meeting_id
        )
        assert result.overall_success is True

    # 3. Verify contradictions/conflicts explainability
    conflicts = gs.get_all_conflicts()
    assert len(conflicts) >= 1
    for conflict in conflicts:
        assert isinstance(conflict.confidence, float)
        assert 0.0 <= conflict.confidence <= 1.0
        assert conflict.reasoning is not None
        assert len(conflict.reasoning.strip()) > 10
        # Check that it's a 2-3 sentence reasoning trace
        sentences = [s.strip() for s in conflict.reasoning.split(".") if s.strip()]
        assert len(sentences) >= 2, f"Reasoning trace should have at least 2 sentences, got: {conflict.reasoning}"

    # 4. Verify stale action items explainability
    briefing_runner = BriefingAgentRunner()
    briefing = briefing_runner.generate_briefing()
    
    stale_items = [ai for ai in briefing.action_items if getattr(ai, "is_stale", False)]
    assert len(stale_items) >= 1
    for ai in stale_items:
        assert isinstance(ai.confidence, float)
        assert 0.0 <= ai.confidence <= 1.0
        assert ai.reasoning is not None
        assert len(ai.reasoning.strip()) > 10
        sentences = [s.strip() for s in ai.reasoning.split(".") if s.strip()]
        assert len(sentences) >= 2, f"Reasoning trace should have at least 2 sentences, got: {ai.reasoning}"
