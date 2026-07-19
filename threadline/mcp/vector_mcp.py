"""
MCP tool server wrapping VectorStore operations.

Exposes domain-specific vector operations (upsert_chunks, search, etc.)
as MCP tools that ADK agents can invoke. This is NOT the generic
mcp-server-qdrant — it wraps our Protocol-defined interface with the
full Threadline domain model (ExtractionResult, SearchResult, etc.).

Usage:
    The vector MCP tools are registered with ADK agents via FunctionTool wrappers.
    In test/mock mode, the tools delegate to InMemoryVectorStore.
    In production, they delegate to QdrantVectorStore (with fallback to InMemory).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from threadline.models import ExtractionResult, SearchResult

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Singleton store reference — set by the agent registry at startup
# ─────────────────────────────────────────────────────────────────────────────

_vector_store = None


def set_vector_store(store) -> None:
    """Set the backing VectorStore instance. Called once at startup."""
    global _vector_store
    _vector_store = store


def get_vector_store():
    """Get the backing VectorStore instance."""
    if _vector_store is None:
        raise RuntimeError(
            "VectorStore not initialized. Call set_vector_store() before using MCP tools."
        )
    return _vector_store


# ─────────────────────────────────────────────────────────────────────────────
# MCP Tool Functions
# ─────────────────────────────────────────────────────────────────────────────

def vector_upsert_chunks(extraction_json: str) -> str:
    """
    Index all facts from an ExtractionResult into the vector store.

    Args:
        extraction_json: JSON-serialized ExtractionResult containing facts
                         to be embedded and indexed.

    Returns:
        JSON object with 'chunks_indexed' count.
    """
    store = get_vector_store()
    from threadline.security import validate_extraction_result
    extraction = ExtractionResult.model_validate_json(extraction_json)
    extraction = validate_extraction_result(extraction)
    count = store.upsert_chunks(extraction)
    return json.dumps({"chunks_indexed": count})


def vector_search(query: str, top_k: int = 5) -> str:
    """
    Perform semantic similarity search over indexed facts.

    Args:
        query: Natural language search query.
        top_k: Maximum number of results to return (default 5).

    Returns:
        JSON array of SearchResult objects with fact_id, text, score,
        meeting_id, speaker, and fact_type.
    """
    store = get_vector_store()
    from threadline.security import sanitize_name
    sanitized_query = sanitize_name(query)
    results = store.search(sanitized_query, top_k=top_k)
    return json.dumps([r.model_dump(mode="json") for r in results])


def vector_get_status() -> str:
    """
    Get the health status of the vector store backend.

    Returns:
        JSON object with connection status, backend type, vector count,
        and embedding model info.
    """
    store = get_vector_store()
    status = store.get_status()
    return json.dumps(status)


# ─────────────────────────────────────────────────────────────────────────────
# Tool registry — list of all vector MCP tools for agent registration
# ─────────────────────────────────────────────────────────────────────────────

VECTOR_MCP_TOOLS = [
    vector_upsert_chunks,
    vector_search,
    vector_get_status,
]
