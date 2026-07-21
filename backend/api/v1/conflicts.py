"""
FastAPI routes for flagged decision conflicts and human-in-the-loop resolution.

This is the endpoint behind the product's headline feature: when the assistant
detects clashing decisions it raises an alarm, and a (non-technical) user
decides how to settle it — keep the current decision, switch to the new one, or
flag it for review with a note.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.deps import get_graph_store
from threadline.graph_store import GraphStore
from threadline.models import ConflictResolutionRequest
from threadline.security import sanitize_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conflicts", tags=["conflicts"])


@router.get("")
async def list_conflicts(graph_store: GraphStore = Depends(get_graph_store)) -> dict:
    """
    Return all conflicts, unresolved first, plus a headline unresolved count
    for the global alert badge.
    """
    conflicts = graph_store.get_all_conflicts()
    conflicts_sorted = sorted(conflicts, key=lambda c: (c.resolved, c.id))
    return {
        "conflicts": [c.model_dump(mode="json") for c in conflicts_sorted],
        "unresolved_count": sum(1 for c in conflicts if not c.resolved),
        "total_count": len(conflicts),
    }


@router.post("/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: str,
    body: ConflictResolutionRequest,
    graph_store: GraphStore = Depends(get_graph_store),
) -> dict:
    """
    Apply a user's decision to a flagged conflict. See ConflictResolutionRequest
    for the `choice` semantics. Persists to the graph; the briefing reflects the
    change on its next fetch.
    """
    note = sanitize_text(body.note) if body.note else None
    logger.info(
        "Conflicts API: resolving %r as %r (by=%s)",
        conflict_id, body.choice, body.resolved_by or "anonymous",
    )
    try:
        result = graph_store.resolve_conflict(
            conflict_id=conflict_id,
            choice=body.choice,
            note=note,
            resolved_by=body.resolved_by,
            keep_decision_id=body.keep_decision_id,
            supersede_decision_id=body.supersede_decision_id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Conflict {conflict_id!r} not found")
    except Exception as e:
        logger.error("Conflicts API: resolve failed for %r: %s", conflict_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to resolve conflict: {e}")

    updated = graph_store.get_conflict(conflict_id)
    return {
        "status": "success",
        "result": result,
        "conflict": updated.model_dump(mode="json") if updated else None,
    }
