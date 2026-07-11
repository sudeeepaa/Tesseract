"""
FastAPI route for executing concept-level semantic searches.
"""
from __future__ import annotations

import logging
from typing import List

from pydantic import BaseModel
from fastapi import APIRouter, Depends

from backend.deps import get_vector_store
from threadline.vector_store import VectorStore
from threadline.models import SearchResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5

class SearchResponse(BaseModel):
    results: List[SearchResult]

@router.post("", response_model=SearchResponse)
async def semantic_search(
    req: SearchRequest,
    vector_store: VectorStore = Depends(get_vector_store)
) -> SearchResponse:
    """
    Execute a semantic search query against indexed meeting facts.
    Returns ranked result objects carrying match scores and source metadata.
    """
    results = vector_store.search(req.query, req.top_k)
    return SearchResponse(results=results)
