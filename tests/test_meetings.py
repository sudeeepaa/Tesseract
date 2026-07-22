"""
Tests for the meetings dashboard: GraphStore.get_all_meetings + the
/api/v1/meetings and /api/v1/meetings/{id}/summary endpoints.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from threadline.config import get_settings, ExtractorBackend, GraphBackend, VectorBackend

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ── InMemory store unit ───────────────────────────────────────────────────────

def test_get_all_meetings_rolls_up_counts(graph_store, mock_extractor, transcript_01, transcript_02):
    for t in (transcript_01, transcript_02):
        graph_store.upsert_result(t, mock_extractor.extract(t, graph_store.get_all_decisions()))

    meetings = graph_store.get_all_meetings()
    ids = [m.id for m in meetings]
    assert ids == ["meeting_01", "meeting_02"]  # chronological by ingestion order

    m1 = meetings[0]
    assert m1.title
    assert m1.decision_count == len([d for d in graph_store.get_all_decisions()
                                     if d.source_meeting_id == "meeting_01"])
    assert m1.ingested_at is not None
    assert m1.preview  # non-empty transcript snippet


# ── API ───────────────────────────────────────────────────────────────────────

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


def test_meetings_endpoint_lists_and_summarizes(client):
    _ingest(client, "meeting_01.txt")
    _ingest(client, "meeting_02.txt")

    listing = client.get("/api/v1/meetings").json()
    assert listing["count"] == 2
    ids = [m["id"] for m in listing["meetings"]]
    assert "meeting_01" in ids and "meeting_02" in ids
    assert all("decision_count" in m for m in listing["meetings"])

    # Summary works in mock mode via the deterministic fallback (no LLM key).
    resp = client.get("/api/v1/meetings/meeting_01/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["meeting_id"] == "meeting_01"
    assert body["summary_markdown"].strip()  # non-empty markdown


def test_summary_unknown_meeting_returns_404(client):
    _ingest(client, "meeting_01.txt")
    resp = client.get("/api/v1/meetings/nope_not_real/summary")
    assert resp.status_code == 404
