"""
Tests for Tesseract Phase 12 Lightweight Async Decoupling.
"""
from __future__ import annotations

import time
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


def test_audio_async_decoupling_flow(client):
    # Post a mock audio file
    mock_audio = b"fake MP3 content"
    response = client.post(
        "/api/v1/pipeline/run",
        files={"file": ("meeting_01.mp3", mock_audio, "audio/mpeg")},
        data={"meeting_id": "meeting_01_audio"}
    )
    
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "IN_PROGRESS"
    assert "status_url" in data
    assert data["meeting_id"] == "meeting_01_audio"

    # Poll status endpoint
    status_url = data["status_url"]
    
    # Give the background task a few cycles to run to completion
    max_retries = 20
    completed = False
    
    for _ in range(max_retries):
        status_resp = client.get(status_url)
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        
        if status_data["status"] == "COMPLETED":
            completed = True
            break
        elif status_data["status"] == "FAILED":
            pytest.fail(f"Background job failed: {status_data.get('progress')}")
            
        time.sleep(0.1)

    assert completed is True
    
    # Retrieve status one more time to verify final shape
    status_resp = client.get(status_url)
    status_data = status_resp.json()
    assert len(status_data["events"]) >= 3
