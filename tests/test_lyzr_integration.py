"""
Integration tests for live Lyzr Studio API connectivity.
"""
from __future__ import annotations

import os
import pytest


@pytest.mark.integration
def test_lyzr_studio_live_integration():
    """
    Test connectivity to the live Lyzr Studio API.
    Only runs if LYZR_API_KEY and LYZR_AGENT_ID environment variables are set.
    """
    api_key = os.getenv("LYZR_API_KEY", "")
    agent_id = os.getenv("LYZR_AGENT_ID", "")
    
    if not api_key:
        pytest.skip("LYZR_API_KEY environment variable not set")
    if not agent_id:
        pytest.skip("LYZR_AGENT_ID environment variable not set")

    try:
        from lyzr import Studio
        
        studio = Studio(api_key=api_key)
        # Attempt to list agents or check connection
        # (Lyzr SDK uses send_message to execute tasks)
        # We send a lightweight test request
        test_payload = {
            "task": "connectivity check",
            "meeting_id": "test_integration_ping",
            "correlation_id": "ping-1234",
            "transcript_text": "Ping transcript contents.",
            "source_file": "ping.txt"
        }
        import json
        response = studio.send_message(
            agent_id=agent_id,
            message=json.dumps(test_payload)
        )
        assert response is not None
        # Either the text response or raw output exists
        resp_text = getattr(response, "response", "") or str(response)
        assert len(resp_text) > 0
        
    except ImportError:
        pytest.fail("lyzr-adk package is not installed but environment keys were provided.")
    except Exception as e:
        pytest.fail(f"Lyzr Studio live integration call failed: {e}")
