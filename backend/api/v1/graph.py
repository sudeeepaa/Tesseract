"""
FastAPI route for retrieving a snapshot of the knowledge graph.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from backend.deps import get_graph_store
from threadline.graph_store import GraphStore
from threadline.models import GraphSnapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graph", tags=["graph"])

@router.get("", response_model=GraphSnapshot)
async def get_graph(graph_store: GraphStore = Depends(get_graph_store)) -> GraphSnapshot:
    """
    Return a snapshot of all nodes and relationships in the knowledge graph.
    Used by the frontend to render interactive network visualizations.
    """
    return graph_store.get_graph_snapshot()
