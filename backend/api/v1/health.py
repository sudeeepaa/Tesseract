"""
FastAPI route for Tesseract Health Check API.
"""
from __future__ import annotations

import os
import logging
from fastapi import APIRouter, Depends
from backend.deps import get_graph_store, get_vector_store
from threadline.graph_store import GraphStore
from threadline.vector_store import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

@router.get("")
async def get_health_status(
    graph_store: GraphStore = Depends(get_graph_store),
    vector_store: VectorStore = Depends(get_vector_store)
) -> dict:
    """
    Tesseract Health Check API. Verifies reachability of Neo4j, Qdrant,
    Lyzr Studio, and Gemini API.
    """
    # 1. Check Graph Store
    graph_status = graph_store.get_status()
    
    # 2. Check Vector Store
    vector_status = vector_store.get_status()

    # 3. Check Lyzr Studio — extraction delegation needs BOTH the API key and a
    #    target agent id, so only report "configured" when both are present.
    lyzr_has_key = bool(os.environ.get("LYZR_API_KEY"))
    lyzr_has_agent = bool(os.environ.get("LYZR_AGENT_ID"))
    lyzr_configured = lyzr_has_key and lyzr_has_agent
    lyzr_status = {
        "configured": lyzr_configured,
        "api_key": lyzr_has_key,
        "agent_id": lyzr_has_agent,
        "status": "healthy" if lyzr_configured else "degraded",
    }

    # 4. Check Gemini API
    gemini_key = os.environ.get("GEMINI_API_KEY")
    gemini_status = {
        "configured": bool(gemini_key),
        "status": "healthy" if gemini_key else "degraded"
    }

    overall = "healthy"
    if not graph_status.get("connected") or not vector_status.get("connected"):
        overall = "degraded"

    return {
        "status": overall,
        "dependencies": {
            "graph_store": graph_status,
            "vector_store": vector_status,
            "lyzr_studio": lyzr_status,
            "gemini_api": gemini_status
        }
    }
