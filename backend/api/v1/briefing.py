"""
FastAPI route for retrieving the compiled executive briefing.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from backend.deps import get_graph_store
from threadline.graph_store import GraphStore
from threadline.briefing import BriefingGenerator
from threadline.models import BriefingOutput

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/briefing", tags=["briefing"])

@router.get("", response_model=BriefingOutput)
async def get_briefing(graph_store: GraphStore = Depends(get_graph_store)) -> BriefingOutput:
    """
    Generate and return the current executive briefing containing structured
    decisions, action items, open conflicts, and the compiled markdown report.
    """
    decisions = graph_store.get_all_decisions()
    actions = graph_store.get_all_action_items()
    conflicts = graph_store.get_all_conflicts()
    topics = graph_store.get_all_topics()
    meeting_count = graph_store.get_meeting_count()

    generator = BriefingGenerator()
    briefing = generator.generate(
        all_decisions=decisions,
        all_action_items=actions,
        all_conflicts=conflicts,
        all_topics=topics,
        meeting_count=meeting_count
    )
    return briefing
