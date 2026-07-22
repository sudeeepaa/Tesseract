"""
FastAPI route for executing concept-level semantic searches.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from backend.deps import get_vector_store, get_graph_store, get_config_settings
from threadline.config import Settings
from threadline.graph_store import GraphStore
from threadline.vector_store import VectorStore
from threadline.models import SearchResult
from threadline.summarizer import summarize_answer, suggest_questions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

# Process-level cache for suggested questions, invalidated when the corpus changes
# (so we only re-call the LLM after new meetings are ingested — not per request).
_SUGGESTIONS: dict[str, Any] = {"signature": None, "questions": []}

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    summarize: bool = True   # set false to skip the LLM answer and return raw hits only

class SearchResponse(BaseModel):
    results: List[SearchResult]
    answer: Optional[str] = None   # LLM-synthesized answer grounded in `results` (None in mock mode)
    grounded: bool = True          # False when the meetings don't actually cover the query

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
    `grounded` is False when the LLM judges the meetings don't cover the query, so the
    UI can suppress the (necessarily non-empty) nearest-neighbour matches.
    """
    results = vector_store.search(req.query, req.top_k)

    answer = None
    grounded = True
    if req.summarize and results:
        # LLM call is blocking — run it off the event loop.
        answer, grounded = await run_in_threadpool(summarize_answer, req.query, results, settings)

    return SearchResponse(results=results, answer=answer, grounded=grounded)


class SuggestionsResponse(BaseModel):
    questions: List[str]


@router.get("/suggestions", response_model=SuggestionsResponse)
async def search_suggestions(
    graph_store: GraphStore = Depends(get_graph_store),
    settings: Settings = Depends(get_config_settings),
) -> SuggestionsResponse:
    """
    Data-grounded example questions for the Ask box. Generated from the current
    decisions/topics/conflicts and cached until the corpus changes, so we don't
    re-call the LLM on every page load.
    """
    decisions = graph_store.get_all_decisions()
    conflicts = graph_store.get_all_conflicts()
    signature = f"{graph_store.get_meeting_count()}:{len(decisions)}:{len(conflicts)}"

    if _SUGGESTIONS["signature"] == signature and _SUGGESTIONS["questions"]:
        return SuggestionsResponse(questions=_SUGGESTIONS["questions"])

    topics = graph_store.get_all_topics()
    questions = await run_in_threadpool(
        suggest_questions, decisions, topics, conflicts, settings
    )
    _SUGGESTIONS["signature"] = signature
    _SUGGESTIONS["questions"] = questions
    return SuggestionsResponse(questions=questions)
