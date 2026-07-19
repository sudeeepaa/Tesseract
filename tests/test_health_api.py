"""
Tests for Tesseract Health Check API.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from threadline.config import get_settings, ExtractorBackend, GraphBackend, VectorBackend


@pytest.fixture
def client():
    settings = get_settings()
    settings.extractor_backend = ExtractorBackend.mock
    settings.graph_backend = GraphBackend.memory
    settings.vector_backend = VectorBackend.memory

    with TestClient(app) as c:
        yield c


def test_health_check_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    
    # Assert top-level fields
    assert "status" in data
    assert data["status"] == "healthy"
    
    assert "dependencies" in data
    deps = data["dependencies"]
    
    # Assert individual dependency structures
    assert "graph_store" in deps
    assert deps["graph_store"]["connected"] is True
    assert deps["graph_store"]["backend"] == "memory"
    
    assert "vector_store" in deps
    assert deps["vector_store"]["connected"] is True
    assert deps["vector_store"]["backend"] == "memory"
    
    assert "lyzr_studio" in deps
    assert "configured" in deps["lyzr_studio"]
    
    assert "gemini_api" in deps
    assert "configured" in deps["gemini_api"]
