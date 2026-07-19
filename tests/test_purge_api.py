"""
Tests for Tesseract GDPR Article 17 Data Governance Purge API.
"""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from threadline.config import get_settings, ExtractorBackend, GraphBackend, VectorBackend


@pytest.fixture
def client_with_data():
    # Configure mock and memory stores
    settings = get_settings()
    settings.extractor_backend = ExtractorBackend.mock
    settings.graph_backend = GraphBackend.memory
    settings.vector_backend = VectorBackend.memory

    with TestClient(app) as c:
        # Populate stores by running pipeline on meeting_01.txt
        # (This populates decisions/action items/entities with Dev Rao, Priya Nair, etc.)
        from pathlib import Path
        meeting_01_path = Path(__file__).parent / "fixtures" / "meeting_01.txt"
        with open(meeting_01_path, "rb") as f:
            resp = c.post(
                "/api/v1/pipeline/run",
                files={"file": ("meeting_01.txt", f, "text/plain")},
                data={"meeting_id": "meeting_01"}
            )
            assert resp.status_code == 200
            print("PIPELINE RUN RESPONSE STATUS:", resp.status_code)
            print("PIPELINE RUN RESPONSE TEXT:", resp.text)
        yield c


def test_purge_cascading_delete_endpoint(client_with_data):
    # Verify Dev Rao exists in decisions/action items/entities before purge
    briefing_resp = client_with_data.get("/api/v1/briefing")
    assert briefing_resp.status_code == 200
    brief_data = briefing_resp.json()
    print("BRIEFING DATA:", json.dumps(brief_data))
    
    # Dev Rao should be owner of React decision
    dev_decisions = [d for d in brief_data["decisions"] if d.get("owner") == "Dev Rao"]
    assert len(dev_decisions) >= 1
    
    # Dev Rao should be assignee of scaffold repo action item
    dev_actions = [a for a in brief_data["action_items"] if a.get("assignee") == "Dev Rao"]
    assert len(dev_actions) >= 1

    # Verify Priya Nair is assignee of deliver wireframes action item (unrelated person)
    priya_actions = [a for a in brief_data["action_items"] if a.get("assignee") == "Priya Nair"]
    assert len(priya_actions) >= 1

    # Call the purge endpoint for "Dev Rao"
    purge_resp = client_with_data.delete("/api/v1/governance/purge/Dev Rao")
    assert purge_resp.status_code == 200
    purge_data = purge_resp.json()
    assert purge_data["status"] == "success"
    
    # Verify graph stats reported deletion
    graph_stats = purge_data["purged_records"]["graph_store"]
    assert graph_stats["removed_entities"] >= 1
    assert graph_stats["updated_decisions"] >= 1
    assert graph_stats["updated_action_items"] >= 1

    # Verify Dev Rao was cleared as owner/assignee but decisions/action items remain
    briefing_after = client_with_data.get("/api/v1/briefing")
    assert briefing_after.status_code == 200
    brief_after_data = briefing_after.json()
    
    # No decision should be owned by Dev Rao anymore
    dev_decisions_after = [d for d in brief_after_data["decisions"] if d.get("owner") == "Dev Rao"]
    assert len(dev_decisions_after) == 0

    # No action item should be assigned to Dev Rao anymore
    dev_actions_after = [a for a in brief_after_data["action_items"] if a.get("assignee") == "Dev Rao"]
    assert len(dev_actions_after) == 0

    # Priya Nair (unrelated) should still be assignee of her action item
    priya_actions_after = [a for a in brief_after_data["action_items"] if a.get("assignee") == "Priya Nair"]
    assert len(priya_actions_after) == 1
