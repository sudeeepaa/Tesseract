"""
Tests for cascade meeting deletion: GraphStore.delete_meeting, VectorStore.delete_meeting, and the DELETE /api/v1/meetings/{id} API endpoint.
"""
from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from threadline.config import get_settings, ExtractorBackend, GraphBackend, VectorBackend

FIXTURES_DIR = Path(__file__).parent / "fixtures"


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


def test_graph_and_vector_delete_meeting_directly(graph_store, vector_store, mock_extractor, transcript_01, transcript_02):
    # 1. Upsert transcripts to populate databases
    for t in (transcript_01, transcript_02):
        res = mock_extractor.extract(t, graph_store.get_all_decisions())
        graph_store.upsert_result(t, res)
        vector_store.upsert_chunks(res)

    # Verify initially populated
    assert len(graph_store.get_all_meetings()) == 2
    assert len(graph_store.get_all_decisions()) > 0
    assert len(vector_store.search("authentication", top_k=100)) > 0

    # 2. Delete meeting_01
    graph_del_stats = graph_store.delete_meeting("meeting_01")
    vector_del_stats = vector_store.delete_meeting("meeting_01")

    assert graph_del_stats["status"] == "success"
    assert graph_del_stats["meeting_id"] == "meeting_01"
    assert vector_del_stats["status"] == "success"
    assert vector_del_stats["meeting_id"] == "meeting_01"

    # Verify only meeting_02 remains
    meetings = graph_store.get_all_meetings()
    assert len(meetings) == 1
    assert meetings[0].id == "meeting_02"

    # Verify decisions from meeting_01 are gone
    m1_decisions = [d for d in graph_store.get_all_decisions() if d.source_meeting_id == "meeting_01"]
    assert len(m1_decisions) == 0

    # Verify vector search results from meeting_01 are gone
    m1_search = [r for r in vector_store.search("authentication", top_k=100) if r.meeting_id == "meeting_01"]
    assert len(m1_search) == 0


def test_delete_meeting_api_endpoint(client):
    # Ingest meetings
    _ingest(client, "meeting_01.txt")
    _ingest(client, "meeting_02.txt")

    # Verify initially exists
    listing = client.get("/api/v1/meetings").json()
    assert listing["count"] == 2

    # Delete meeting_01
    resp = client.delete("/api/v1/meetings/meeting_01")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert "Successfully deleted meeting" in body["message"]

    # Verify listing shows only 1 meeting remaining
    listing = client.get("/api/v1/meetings").json()
    assert listing["count"] == 1
    assert listing["meetings"][0]["id"] == "meeting_02"

    # Verify 404 on deleting non-existent meeting
    resp = client.delete("/api/v1/meetings/nope_not_real")
    assert resp.status_code == 404
