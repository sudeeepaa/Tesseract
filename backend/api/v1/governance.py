"""
FastAPI route for Tesseract Data Governance API (GDPR Article 17 Purge).
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from backend.deps import get_graph_store, get_vector_store
from threadline.graph_store import GraphStore
from threadline.vector_store import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/governance", tags=["governance"])

@router.delete("/purge/{person_name}")
async def purge_person_data(
    person_name: str,
    graph_store: GraphStore = Depends(get_graph_store),
    vector_store: VectorStore = Depends(get_vector_store)
) -> dict:
    """
    GDPR Article 17 Purge API. Cascades deletion of the specified person
    and clear ownership fields from both Graph and Vector stores.
    """
    logger.info("Governance API: Purging all data for person %r", person_name)
    try:
        graph_stats = graph_store.purge_person(person_name)
        vector_stats = vector_store.purge_person(person_name)
        return {
            "status": "success",
            "message": f"Successfully purged all data for person '{person_name}'",
            "purged_records": {
                "graph_store": graph_stats,
                "vector_store": vector_stats
            }
        }
    except Exception as e:
        logger.error("Governance API: Purge failed for %r: %s", person_name, e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute GDPR purge cascading delete: {str(e)}"
        )


@router.post("/reset-vectors")
async def reset_vectors(
    vector_store: VectorStore = Depends(get_vector_store),
) -> dict:
    """
    Wipe and rebuild the vector index from scratch. Recovery tool for vectors
    orphaned by meetings deleted or reset outside the normal cascade (their
    owning meeting no longer exists anywhere to filter a delete by) — those
    points linger forever and pollute every search result. Re-ingest meetings
    afterward to rebuild the index.
    """
    logger.warning("Governance API: full vector store reset requested")
    try:
        result = vector_store.reset_all()
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error("Governance API: vector reset failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to reset vector store: {str(e)}")
