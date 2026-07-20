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
    from dotenv import load_dotenv
    load_dotenv(".env", override=True)
    
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        pytest.skip("GEMINI_API_KEY environment variable not set")

    try:
        import google.generativeai as genai
        
        genai.configure(api_key=api_key)
        
        # Dynamically list models supporting generateContent
        available_models = [
            m.name.split("/")[-1] 
            for m in genai.list_models() 
            if "generateContent" in m.supported_generation_methods
        ]
        
        # Sort by preferred models first to keep tests clean
        preferred = ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-flash-latest"]
        models_to_try = [p for p in preferred if p in available_models]
        # Append other available models
        for m in available_models:
            if m not in models_to_try:
                models_to_try.append(m)
                
        if not models_to_try:
            pytest.fail("No models found supporting generateContent for this API key.")
            
        # Try models in order until one succeeds
        last_error = None
        for selected_model in models_to_try:
            try:
                model = genai.GenerativeModel(selected_model)
                response = model.generate_content("Ping. Reply with exactly the word Pong.")
                if response and response.text:
                    assert "pong" in response.text.lower()
                    return # SUCCESS!
            except Exception as e:
                last_error = e
                continue
                
        # If we get here, all models failed
        pytest.fail(f"All available models failed generateContent. Last error: {last_error}")
        
    except ImportError:
        pytest.fail("google-generativeai package is not installed but GEMINI_API_KEY was provided.")
    except Exception as e:
        pytest.fail(f"Gemini API live integration call failed: {e}")
