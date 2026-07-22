"""
FastAPI route for executing concept-level semantic searches.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from backend.deps import get_vector_store, get_config_settings
from threadline.config import Settings
from threadline.vector_store import VectorStore
from threadline.models import SearchResult
from threadline.summarizer import summarize_answer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    summarize: bool = True   # set false to skip the LLM answer and return raw hits only

class SearchResponse(BaseModel):
    results: List[SearchResult]
    answer: Optional[str] = None   # LLM-synthesized answer grounded in `results` (None in mock mode)

@router.post("", response_model=SearchResponse)
async def semantic_search(
    req: SearchRequest,
    vector_store: VectorStore = Depends(get_vector_store),
    settings: Settings = Depends(get_config_settings),
) -> SearchResponse:
    """
    Execute a semantic search query against indexed meeting facts.
    Returns ranked result objects carrying match scores and source metadata, plus a
    short LLM-synthesized answer grounded in those results (when an LLM is configured).
    """
    results = vector_store.search(req.query, req.top_k)

    answer = None
    if req.summarize and results:
        # LLM call is blocking — run it off the event loop.
        answer = await run_in_threadpool(summarize_answer, req.query, results, settings)

    return SearchResponse(results=results, answer=answer)
