"""
FastAPI routes for the meetings dashboard: list meetings + per-meeting LLM summary.
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from backend.deps import get_graph_store, get_config_settings
from threadline.config import Settings
from threadline.graph_store import GraphStore
from threadline.models import MeetingSummary
from threadline.summarizer import summarize_meeting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["meetings"])


class MeetingsResponse(BaseModel):
    meetings: List[MeetingSummary]
    count: int


class MeetingSummaryResponse(BaseModel):
    meeting_id: str
    title: str
    summary_markdown: str


@router.get("", response_model=MeetingsResponse)
async def list_meetings(
    graph_store: GraphStore = Depends(get_graph_store),
) -> MeetingsResponse:
    """List every meeting ingested so far, chronologically, with rollup counts."""
    meetings = graph_store.get_all_meetings()
    return MeetingsResponse(meetings=meetings, count=len(meetings))


@router.get("/{meeting_id}/summary", response_model=MeetingSummaryResponse)
async def meeting_summary(
    meeting_id: str,
    graph_store: GraphStore = Depends(get_graph_store),
    settings: Settings = Depends(get_config_settings),
) -> MeetingSummaryResponse:
    """
    Return the meeting's summary. It is normally generated once at ingestion and
    cached on the meeting, so this call does no LLM work. If a meeting has no
    cached summary yet (e.g. ingested before caching, or via the direct pipeline),
    it is generated once here and stored.
    """
    meetings = {m.id: m for m in graph_store.get_all_meetings()}
    meeting = meetings.get(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' not found")

    if meeting.summary:
        return MeetingSummaryResponse(
            meeting_id=meeting_id, title=meeting.title, summary_markdown=meeting.summary
        )

    # Cache miss → generate once (blocking LLM call off the event loop) and store.
    decisions = [d for d in graph_store.get_all_decisions() if d.source_meeting_id == meeting_id]
    action_items = [a for a in graph_store.get_all_action_items() if a.source_meeting_id == meeting_id]
    summary = await run_in_threadpool(
        summarize_meeting, meeting.title, decisions, action_items, [], settings
    )
    try:
        graph_store.set_meeting_summary(meeting_id, summary)
    except Exception:  # noqa: BLE001
        pass
    return MeetingSummaryResponse(
        meeting_id=meeting_id, title=meeting.title, summary_markdown=summary
    )
