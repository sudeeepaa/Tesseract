"""
FastAPI routes for per-decision human review.

Lets a user weigh in on any single decision directly — Approve (endorse →
confirmed), Reject (overturn → reversed), or add a plain Comment — independent
of the conflict-resolution flow. Backed by GraphStore.review_decision in both
the InMemory and Neo4j stores.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.deps import get_graph_store
from threadline.graph_store import GraphStore
from threadline.models import DecisionReviewRequest
from threadline.security import sanitize_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.post("/{decision_id}/review")
async def review_decision(
    decision_id: str,
    body: DecisionReviewRequest,
    graph_store: GraphStore = Depends(get_graph_store),
) -> dict:
    """
    Apply a human review to a single decision. See DecisionReviewRequest for
    the `action` semantics (approve | reject | comment). Persists to the graph;
    the briefing reflects the change on its next fetch.
    """
    if body.action not in ("approve", "reject", "comment"):
        raise HTTPException(status_code=400, detail=f"Unknown action {body.action!r}")
    note = sanitize_text(body.note) if body.note else None
    logger.info(
        "Decisions API: reviewing %r as %r (by=%s)",
        decision_id, body.action, body.reviewed_by or "anonymous",
    )
    try:
        result = graph_store.review_decision(
            decision_id=decision_id,
            action=body.action,
            note=note,
            reviewed_by=body.reviewed_by,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id!r} not found")
    except Exception as e:
        logger.error("Decisions API: review failed for %r: %s", decision_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to review decision: {e}")

    return {"status": "success", "result": result}
