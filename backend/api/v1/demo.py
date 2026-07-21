"""
Demo seeding — one-click "Load sample meetings" for the UI.

Loads the first three bundled sample meetings (kickoff → sprint review →
security review). This deliberately stops before the fourth meeting so the
Auth0-vs-GDPR conflict stays OPEN — letting a user resolve it live, which is
the whole point of the human-in-the-loop feature.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from backend.deps import get_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/demo", tags=["demo"])

# backend/api/v1/demo.py → repo root → tests/fixtures
_FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures"


@router.post("/seed")
async def seed_demo(full: bool = False, pipeline=Depends(get_pipeline)) -> dict:
    """
    Process the sample meetings through the live pipeline.

    By default loads meetings 1–3 (leaves the conflict open). Pass ?full=true
    to also load meeting 4, which resolves the conflict automatically.
    """
    files = sorted(_FIXTURES.glob("meeting_*.txt"))
    if not files:
        raise HTTPException(status_code=404, detail="No sample meetings are bundled with this build.")
    if not full:
        files = files[:3]

    processed = []
    for p in files:
        try:
            result = pipeline.run_sync(source=p.name, meeting_id=p.stem, content=p.read_bytes())
            processed.append({"meeting_id": p.stem, "success": not result.errors})
        except Exception as e:
            logger.error("Demo seed failed for %s: %s", p.name, e)
            processed.append({"meeting_id": p.stem, "success": False, "error": str(e)})

    return {
        "status": "success",
        "meetings_loaded": sum(1 for m in processed if m["success"]),
        "details": processed,
    }
