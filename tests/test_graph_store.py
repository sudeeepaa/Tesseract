"""
Tests for graph_store.py and graph_store_neo4j.py
"""
from __future__ import annotations

import os
import pytest

from threadline.graph_store import InMemoryGraphStore
from threadline.models import (
    MeetingTranscript,
    ExtractionResult,
    Decision,
    DecisionStatus,
    ActionItem,
    ActionItemStatus,
    PriorDecisionUpdate,
    SupersessionRecord,
    ConflictRecord,
)

# ── InMemoryGraphStore Unit Tests ─────────────────────────────────────────────

def test_in_memory_store_lifecycle():
    store = InMemoryGraphStore()
    assert store.get_meeting_count() == 0
    assert len(store.get_all_decisions()) == 0

    t1 = MeetingTranscript(id="m1", source_file="m1.txt", text="Test 1")
    d1 = Decision(id="d1", text="Decision 1", status=DecisionStatus.confirmed, source_meeting_id="m1")
    
    r1 = ExtractionResult(
        meeting_id="m1",
        decisions=[d1],
    )
    
    stats = store.upsert_result(t1, r1)
    assert stats["new_nodes"] == 1  # 1 decision (meeting node exists but is not tracked as new_nodes)
    assert store.get_meeting_count() == 1
    assert len(store.get_all_decisions()) == 1
    assert store.get_all_decisions()[0].id == "d1"

    # Now verify prior decision updates
    t2 = MeetingTranscript(id="m2", source_file="m2.txt", text="Test 2")
    pu = PriorDecisionUpdate(
        decision_id="d1",
        decision_text="Decision 1",
        new_status=DecisionStatus.under_review,
        reason="Needs evaluation"
    )
    r2 = ExtractionResult(
        meeting_id="m2",
        prior_decision_updates=[pu]
    )
    store.upsert_result(t2, r2)
    
    decisions = store.get_all_decisions()
    assert len(decisions) == 1
    assert decisions[0].status == DecisionStatus.under_review


# ── Neo4jGraphStore Integration Tests ─────────────────────────────────────────

@pytest.mark.integration
def test_neo4j_store_integration():
    from threadline.graph_store_neo4j import Neo4jGraphStore
    
    from dotenv import load_dotenv
    load_dotenv(".env", override=True)
    
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME") or "neo4j"
    pwd = os.getenv("NEO4J_PASSWORD", "threadline_dev")
    
    store = Neo4jGraphStore(uri=uri, user=user, password=pwd)
    try:
        store.verify_connectivity()
    except Exception as e:
        pytest.skip(f"Neo4j database not reachable: {e}")

    # Wipe database for clean test run
    with store.driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")

    # Run simple ingestion test
    t = MeetingTranscript(id="integration_m1", source_file="int.txt", text="Initial text")
    d = Decision(id="int_d1", text="Decision 1", status=DecisionStatus.confirmed, source_meeting_id="integration_m1")
    r = ExtractionResult(meeting_id="integration_m1", decisions=[d])
    
    stats = store.upsert_result(t, r)
    assert stats["total_decisions"] == 1
    
    decs = store.get_all_decisions()
    assert len(decs) == 1
    assert decs[0].id == "int_d1"
    
    assert store.get_meeting_count() == 1
    
    # Close connection
    store.close()
