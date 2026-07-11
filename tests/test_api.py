"""
API integration tests for all FastAPI endpoints.
"""
from __future__ import annotations

import json
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from backend.main import app
from threadline.config import get_settings, Settings, ExtractorBackend, GraphBackend, VectorBackend

FIXTURES_DIR = Path(__file__).parent / "fixtures"

@pytest.fixture
def client():
    # Force mock and memory settings to ensure zero external service dependencies
    settings = get_settings()
    settings.extractor_backend = ExtractorBackend.mock
    settings.graph_backend = GraphBackend.memory
    settings.vector_backend = VectorBackend.memory

    with TestClient(app) as c:
        yield c

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Threadline" in response.json()["app"]

def test_status_endpoint(client):
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["neo4j"]["backend"] == "memory"
    assert data["qdrant"]["backend"] == "memory"
    assert data["llm"]["backend"] == "mock"

def test_pipeline_run_and_downstream_read(client):
    # Upload transcript file to the pipeline
    meeting_01_path = FIXTURES_DIR / "meeting_01.txt"
    with open(meeting_01_path, "rb") as f:
        response = client.post(
            "/api/v1/pipeline/run",
            files={"file": ("meeting_01.txt", f, "text/plain")},
            data={"meeting_id": "meeting_01"}
        )
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    # Read SSE events from streaming response body
    lines = response.text.splitlines()
    events = []
    for line in lines:
        if line.startswith("data: "):
            ev_data = json.loads(line[6:])
            events.append(ev_data)
            
    assert len(events) > 0
    stages = [ev["stage"] for ev in events]
    assert "INGEST" in stages
    assert "EXTRACT" in stages
    assert "GRAPH_WRITE" in stages
    assert "VECTOR_WRITE" in stages
    assert "BRIEFING" in stages
    assert "PIPELINE" in stages

    # Check briefing endpoint
    response_brief = client.get("/api/v1/briefing")
    assert response_brief.status_code == 200
    brief_data = response_brief.json()
    assert len(brief_data["decisions"]) >= 4
    assert brief_data["meeting_count"] == 1
    assert "React" in brief_data["markdown"]

    # Check graph endpoint
    response_graph = client.get("/api/v1/graph")
    assert response_graph.status_code == 200
    graph_data = response_graph.json()
    assert len(graph_data["nodes"]) >= 5
    assert len(graph_data["edges"]) >= 4

    # Check search endpoint
    response_search = client.post(
        "/api/v1/search",
        json={"query": "database choice", "top_k": 3}
    )
    assert response_search.status_code == 200
    search_data = response_search.json()
    assert "results" in search_data
    assert len(search_data["results"]) >= 1
