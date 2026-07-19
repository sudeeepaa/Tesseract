"""
Integration tests for live Gemini API connectivity.
"""
from __future__ import annotations

import os
import pytest


@pytest.mark.integration
def test_gemini_api_live_integration():
    """
    Test connectivity to the live Gemini generative model API.
    Only runs if GEMINI_API_KEY environment variable is set.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        pytest.skip("GEMINI_API_KEY environment variable not set")

    try:
        import google.generativeai as genai
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        # Make a simple, low-cost content generation call
        response = model.generate_content("Ping. Reply with exactly the word Pong.")
        assert response is not None
        assert "pong" in response.text.lower()
        
    except ImportError:
        pytest.fail("google-generativeai package is not installed but GEMINI_API_KEY was provided.")
    except Exception as e:
        pytest.fail(f"Gemini API live integration call failed: {e}")
