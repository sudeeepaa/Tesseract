"""
Tests for the human-in-the-loop conflict resolution loop:
  • InMemoryGraphStore.resolve_conflict / get_conflict
  • POST /api/v1/conflicts/{id}/resolve  and  GET /api/v1/conflicts
  • Neo4j resolve (integration, behind THREADLINE_INTEGRATION=1)

The demo scenario: meeting_01 confirms "Use Auth0" (dec_m1_04); meeting_03
raises a GDPR conflict against it (conflict_01, unresolved). A user then
settles that conflict from the UI.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from threadline.config import get_settings, ExtractorBackend, GraphBackend, VectorBackend
from threadline.graph_store import InMemoryGraphStore
from threadline.models import DecisionStatus

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _seed_conflict(graph_store, mock_extractor, transcript_01, transcript_03):
    """Ingest m1 then m3 so an unresolved conflict (Auth0 vs GDPR) exists."""
    r1 = mock_extractor.extract(transcript_01, [])
    graph_store.upsert_result(transcript_01, r1)
    existing = graph_store.get_all_decisions()
    r3 = mock_extractor.extract(transcript_03, existing)
    graph_store.upsert_result(transcript_03, r3)
    conflicts = graph_store.get_all_conflicts()
    assert conflicts, "expected meeting_03 to seed a conflict"
    return conflicts[0]


def _auth0(graph_store):
    return next(d for d in graph_store.get_all_decisions() if d.id == "dec_m1_04")


# ── InMemory unit tests ───────────────────────────────────────────────────────

def test_seeded_conflict_is_unresolved(graph_store, mock_extractor, transcript_01, transcript_03):
    c = _seed_conflict(graph_store, mock_extractor, transcript_01, transcript_03)
    assert c.resolved is False
    assert c.fact_a_id == "dec_m1_04"


def test_resolve_keep_marks_resolved_and_confirms(graph_store, mock_extractor, transcript_01, transcript_03):
    c = _seed_conflict(graph_store, mock_extractor, transcript_01, transcript_03)
    result = graph_store.resolve_conflict(
        c.id, choice="keep", keep_decision_id="dec_m1_04", resolved_by="Sam",
    )
    assert result["resolved"] is True

    updated = graph_store.get_conflict(c.id)
    assert updated.resolved is True
    assert updated.resolution_choice == "keep"
    assert updated.resolved_by == "Sam"
    assert updated.resolved_at is not None
    assert _auth0(graph_store).status == DecisionStatus.confirmed


def test_resolve_switch_supersedes_old(graph_store, mock_extractor, transcript_01, transcript_03):
    c = _seed_conflict(graph_store, mock_extractor, transcript_01, transcript_03)
    result = graph_store.resolve_conflict(
        c.id, choice="switch", supersede_decision_id="dec_m1_04",
    )
    assert result["resolved"] is True
    assert result["updated_decisions"] >= 1
    assert _auth0(graph_store).status == DecisionStatus.superseded
    assert graph_store.get_conflict(c.id).resolved is True


def test_resolve_review_keeps_open_and_flags(graph_store, mock_extractor, transcript_01, transcript_03):
    c = _seed_conflict(graph_store, mock_extractor, transcript_01, transcript_03)
    result = graph_store.resolve_conflict(
        c.id, choice="review", keep_decision_id="dec_m1_04",
        note="Ask legal to confirm `DROP` residency; {sensitive}",
    )
    # "review" does NOT resolve — it stays flagged for attention.
    assert result["resolved"] is False
    updated = graph_store.get_conflict(c.id)
    assert updated.resolved is False
    assert updated.resolution_note is not None
    # Note was sanitized-safe at the API layer; store keeps raw text here.
    assert _auth0(graph_store).status == DecisionStatus.under_review


def test_resolve_unknown_conflict_raises(graph_store):
    with pytest.raises(KeyError):
        graph_store.resolve_conflict("does_not_exist", choice="keep")


# ── API tests ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    settings = get_settings()
    settings.extractor_backend = ExtractorBackend.mock
    settings.graph_backend = GraphBackend.memory
    settings.vector_backend = VectorBackend.memory
    with TestClient(app) as c:
        yield c


def _ingest(client, name):
    with open(FIXTURES_DIR / name, "rb") as f:
        r = client.post(
            "/api/v1/pipeline/run",
            files={"file": (name, f, "text/plain")},
            data={"meeting_id": name.replace(".txt", "")},
        )
    assert r.status_code == 200
    return r


def test_conflicts_list_and_resolve_endpoint(client):
    _ingest(client, "meeting_01.txt")
    _ingest(client, "meeting_03.txt")

    # List surfaces the unresolved conflict + a headline count for the alert bell.
    listing = client.get("/api/v1/conflicts").json()
    assert listing["unresolved_count"] >= 1
    conflict = next(c for c in listing["conflicts"] if not c["resolved"])

    # Resolve it via the endpoint.
    resp = client.post(
        f"/api/v1/conflicts/{conflict['id']}/resolve",
        json={"choice": "switch", "supersede_decision_id": "dec_m1_04",
              "resolved_by": "Sam", "note": "Switching to Keycloak"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["conflict"]["resolved"] is True

    # Briefing reflects the change: Auth0 now superseded, conflict resolved.
    brief = client.get("/api/v1/briefing").json()
    auth0 = next((d for d in brief["decisions"] if d["id"] == "dec_m1_04"), None)
    assert auth0 is not None and auth0["status"] == "superseded"

    # Alert count drops.
    assert client.get("/api/v1/conflicts").json()["unresolved_count"] == \
        listing["unresolved_count"] - 1


def test_resolve_missing_conflict_returns_404(client):
    _ingest(client, "meeting_01.txt")
    resp = client.post("/api/v1/conflicts/nope_not_real/resolve", json={"choice": "keep"})
    assert resp.status_code == 404


# ── Neo4j integration ─────────────────────────────────────────────────────────

@pytest.mark.integration
def test_neo4j_resolve_conflict(mock_extractor, transcript_01, transcript_03):
    from threadline.graph_store_neo4j import Neo4jGraphStore

    store = Neo4jGraphStore(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "threadline_dev"),
    )
    try:
        store.verify_connectivity()
    except Exception as e:
        pytest.skip(f"Neo4j not reachable: {e}")

    with store.driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")

    c = _seed_conflict(store, mock_extractor, transcript_01, transcript_03)
    result = store.resolve_conflict(
        c.id, choice="switch", supersede_decision_id="dec_m1_04", resolved_by="Sam",
    )
    assert result["resolved"] is True
    assert store.get_conflict(c.id).resolved is True
    auth0 = next(d for d in store.get_all_decisions() if d.id == "dec_m1_04")
    assert auth0.status == DecisionStatus.superseded
    store.close()
