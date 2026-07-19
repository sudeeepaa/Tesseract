"""
MCP tool server wrapping GraphStore operations.

Exposes domain-specific graph operations (upsert_result, get_all_decisions, etc.)
as MCP tools that ADK agents can invoke. This is NOT the generic neo4j-mcp-server —
it wraps our Protocol-defined interface with the full Threadline domain model.

Usage:
    The graph MCP tools are registered with ADK agents via FunctionTool wrappers.
    In test/mock mode, the tools delegate to InMemoryGraphStore.
    In production, they delegate to Neo4jGraphStore (with fallback to InMemory).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from threadline.models import (
    ActionItem,
    ConflictRecord,
    Decision,
    ExtractionResult,
    GraphSnapshot,
    MeetingTranscript,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Singleton store reference — set by the agent registry at startup
# ─────────────────────────────────────────────────────────────────────────────

_graph_store = None


def set_graph_store(store) -> None:
    """Set the backing GraphStore instance. Called once at startup."""
    global _graph_store
    _graph_store = store


def get_graph_store():
    """Get the backing GraphStore instance."""
    if _graph_store is None:
        raise RuntimeError(
            "GraphStore not initialized. Call set_graph_store() before using MCP tools."
        )
    return _graph_store


# ─────────────────────────────────────────────────────────────────────────────
# MCP Tool Functions
#
# These are plain Python functions with type hints and docstrings.
# They will be wrapped as google.adk FunctionTool objects when registered
# with an ADK agent, or exposed via the MCP SDK for standalone server mode.
# ─────────────────────────────────────────────────────────────────────────────

def graph_upsert_extraction(
    meeting_id: str,
    source_file: str,
    transcript_text: str,
    extraction_json: str,
) -> str:
    """
    Persist an ExtractionResult into the knowledge graph.

    Args:
        meeting_id: Unique meeting identifier.
        source_file: Original source file path.
        transcript_text: Full transcript text.
        extraction_json: JSON-serialized ExtractionResult.

    Returns:
        JSON string with write statistics (new_nodes, new_edges, etc.).
    """
    store = get_graph_store()
    transcript = MeetingTranscript(
        id=meeting_id,
        source_file=source_file,
        text=transcript_text,
        meeting_title=meeting_id.replace("_", " ").title(),
    )
    from threadline.security import validate_extraction_result, validate_meeting_transcript
    extraction = ExtractionResult.model_validate_json(extraction_json)
    extraction = validate_extraction_result(extraction)
    transcript = validate_meeting_transcript(transcript)
    stats = store.upsert_result(transcript, extraction)
    return json.dumps(stats)


def graph_get_all_decisions() -> str:
    """
    Retrieve all decisions from the knowledge graph.

    Returns:
        JSON array of Decision objects with id, text, status, owner,
        source_meeting_id, and relationship fields.
    """
    store = get_graph_store()
    decisions = store.get_all_decisions()
    return json.dumps([d.model_dump(mode="json") for d in decisions])


def graph_get_all_action_items() -> str:
    """
    Retrieve all action items from the knowledge graph.

    Returns:
        JSON array of ActionItem objects.
    """
    store = get_graph_store()
    items = store.get_all_action_items()
    return json.dumps([ai.model_dump(mode="json") for ai in items])


def graph_get_all_conflicts() -> str:
    """
    Retrieve all conflict records from the knowledge graph.

    Returns:
        JSON array of ConflictRecord objects including resolution status.
    """
    store = get_graph_store()
    conflicts = store.get_all_conflicts()
    return json.dumps([c.model_dump(mode="json") for c in conflicts])


def graph_get_all_topics() -> str:
    """
    Retrieve all topic names from the knowledge graph.

    Returns:
        JSON array of topic name strings.
    """
    store = get_graph_store()
    topics = store.get_all_topics()
    return json.dumps(topics)


def graph_get_meeting_count() -> str:
    """
    Get the total number of meetings processed.

    Returns:
        JSON object with 'count' field.
    """
    store = get_graph_store()
    count = store.get_meeting_count()
    return json.dumps({"count": count})


def graph_get_snapshot() -> str:
    """
    Get a full graph snapshot for visualization.

    Returns:
        JSON object with 'nodes' and 'edges' arrays for the graph UI.
    """
    store = get_graph_store()
    snapshot = store.get_graph_snapshot()
    return snapshot.model_dump_json()


def graph_get_status() -> str:
    """
    Get the health status of the graph store backend.

    Returns:
        JSON object with connection status, backend type, and counts.
    """
    store = get_graph_store()
    status = store.get_status()
    return json.dumps(status)


# ─────────────────────────────────────────────────────────────────────────────
# Tool registry — list of all graph MCP tools for agent registration
# ─────────────────────────────────────────────────────────────────────────────

GRAPH_MCP_TOOLS = [
    graph_upsert_extraction,
    graph_get_all_decisions,
    graph_get_all_action_items,
    graph_get_all_conflicts,
    graph_get_all_topics,
    graph_get_meeting_count,
    graph_get_snapshot,
    graph_get_status,
]
