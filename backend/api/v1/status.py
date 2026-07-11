"""
FastAPI route for checking backend connectivity and status.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends

from backend.deps import get_graph_store, get_vector_store, get_config_settings
from threadline.graph_store import GraphStore
from threadline.vector_store import VectorStore
from threadline.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/status", tags=["status"])

@router.get("", response_model=Dict[str, Any])
async def get_status(
    settings: Settings = Depends(get_config_settings),
    graph_store: GraphStore = Depends(get_graph_store),
    vector_store: VectorStore = Depends(get_vector_store)
) -> Dict[str, Any]:
    """
    Return health details of Neo4j, Qdrant, and the configured LLM extractor.
    Enables the frontend to display backend connectivity state.
    """
    gs_status = graph_store.get_status()
    vs_status = vector_store.get_status()
    ex_backend = settings.effective_extractor_backend.value

    return {
        "neo4j": {
            "connected": gs_status.get("connected", False),
            "node_count": gs_status.get("node_count", 0),
            "edge_count": gs_status.get("edge_count", 0),
            "backend": gs_status.get("backend", "memory"),
            "error": gs_status.get("error"),
        },
        "qdrant": {
            "connected": vs_status.get("connected", False),
            "vector_count": vs_status.get("vector_count", 0),
            "backend": vs_status.get("backend", "memory"),
            "error": vs_status.get("error"),
        },
        "llm": {
            "backend": ex_backend,
        }
    }
