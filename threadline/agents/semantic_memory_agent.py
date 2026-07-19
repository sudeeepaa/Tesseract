"""
Semantic Memory Agent — Google ADK Agent + A2A Server.

Receives an ExtractionResult and indexes all facts into the vector store
via MCP tools (vector_mcp). This agent replaces the direct
VectorStore.upsert_chunks() call that the Pipeline class previously made.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from threadline.models import ExtractionResult
from threadline.mcp.vector_mcp import vector_upsert_chunks

logger = logging.getLogger(__name__)

AGENT_NAME = "semantic_memory_agent"
AGENT_DESCRIPTION = (
    "Indexes meeting facts into the semantic vector store for similarity search. "
    "Embeds extracted facts (decisions, action items) and stores them for later "
    "retrieval. Uses MCP tools for all vector operations."
)


class SemanticMemoryAgentRunner:
    """
    Encapsulates the Semantic Memory Agent's logic.
    Delegates to MCP vector tools for indexing.
    """

    def index(self, extraction: ExtractionResult) -> dict[str, Any]:
        """
        Index all facts from an ExtractionResult.

        Args:
            extraction: The extraction result containing facts to index.

        Returns:
            Dict with indexing statistics.
        """
        result_json = vector_upsert_chunks(extraction.model_dump_json())
        result = json.loads(result_json)
        logger.info(
            "Semantic Memory: indexed %d chunks for meeting %s",
            result["chunks_indexed"], extraction.meeting_id,
        )
        return result


def vector_index_tool(extraction_json: str) -> str:
    """
    ADK tool function: Index extraction results into the vector store.

    Args:
        extraction_json: JSON-serialized ExtractionResult containing facts
                         to be embedded and indexed.

    Returns:
        JSON string with indexing statistics.
    """
    extraction = ExtractionResult.model_validate_json(extraction_json)
    runner = SemanticMemoryAgentRunner()
    stats = runner.index(extraction)
    return json.dumps(stats)


# ─────────────────────────────────────────────────────────────────────────────
# ADK Agent creation
# ─────────────────────────────────────────────────────────────────────────────

def create_semantic_memory_adk_agent():
    """Create a Google ADK Agent for semantic memory indexing."""
    try:
        from google.adk.agents import Agent

        agent = Agent(
            name=AGENT_NAME,
            model="gemini-2.0-flash",
            description=AGENT_DESCRIPTION,
            instruction=(
                "You are the Semantic Memory Agent for the Threadline meeting intelligence system. "
                "When given extraction results, call the vector_index_tool to index all facts "
                "into the vector store. Return the indexing statistics as-is."
            ),
            tools=[vector_index_tool],
        )
        logger.info("Created ADK Semantic Memory Agent: %s", AGENT_NAME)
        return agent
    except ImportError:
        logger.warning("google-adk not installed — Semantic Memory ADK agent unavailable")
        return None


def create_semantic_memory_a2a_app():
    """Create an A2A ASGI application for the Semantic Memory Agent."""
    agent = create_semantic_memory_adk_agent()
    if agent is None:
        raise RuntimeError("Cannot create A2A app: google-adk not available")
    try:
        from google.adk.a2a import to_a2a
        return to_a2a(agent)
    except ImportError:
        raise RuntimeError("google-adk[a2a] not installed")
