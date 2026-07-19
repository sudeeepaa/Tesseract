"""
Graph Writer Agent — Google ADK Agent + A2A Server.

Receives an ExtractionResult and persists it into the knowledge graph
via MCP tools (graph_mcp). This agent replaces the direct
GraphStore.upsert_result() call that the Pipeline class previously made.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from threadline.models import ExtractionResult, MeetingTranscript
from threadline.mcp.graph_mcp import graph_upsert_extraction

logger = logging.getLogger(__name__)

AGENT_NAME = "graph_writer_agent"
AGENT_DESCRIPTION = (
    "Persists meeting extraction results into the knowledge graph. "
    "Creates decision nodes, action items, entities, topics, conflict records, "
    "and supersession edges. Uses MCP tools for all graph operations."
)


class GraphWriterAgentRunner:
    """
    Encapsulates the Graph Writer Agent's logic.
    Delegates to MCP graph tools for persistence.
    """

    def write(
        self,
        meeting_id: str,
        source_file: str,
        transcript_text: str,
        extraction: ExtractionResult,
    ) -> dict[str, Any]:
        """
        Persist an ExtractionResult into the knowledge graph.

        Args:
            meeting_id: Unique meeting identifier.
            source_file: Original source file path.
            transcript_text: Full transcript text.
            extraction: The extraction result to persist.

        Returns:
            Dict with write statistics (new_nodes, new_edges, etc.).
        """
        stats_json = graph_upsert_extraction(
            meeting_id=meeting_id,
            source_file=source_file,
            transcript_text=transcript_text,
            extraction_json=extraction.model_dump_json(),
        )
        stats = json.loads(stats_json)
        logger.info(
            "Graph Writer: persisted meeting %s — %s",
            meeting_id, stats.get("summary", "done"),
        )
        return stats


def graph_write_tool(
    meeting_id: str,
    source_file: str,
    transcript_text: str,
    extraction_json: str,
) -> str:
    """
    ADK tool function: Persist extraction results into the knowledge graph.

    Args:
        meeting_id: Unique meeting identifier.
        source_file: Original source file path.
        transcript_text: Full transcript text.
        extraction_json: JSON-serialized ExtractionResult.

    Returns:
        JSON string with write statistics.
    """
    extraction = ExtractionResult.model_validate_json(extraction_json)
    runner = GraphWriterAgentRunner()
    stats = runner.write(meeting_id, source_file, transcript_text, extraction)
    return json.dumps(stats)


# ─────────────────────────────────────────────────────────────────────────────
# ADK Agent creation
# ─────────────────────────────────────────────────────────────────────────────

def create_graph_writer_adk_agent():
    """Create a Google ADK Agent for graph writing."""
    try:
        from google.adk.agents import Agent

        agent = Agent(
            name=AGENT_NAME,
            model="gemini-2.0-flash",
            description=AGENT_DESCRIPTION,
            instruction=(
                "You are the Graph Writer Agent for the Tesseract meeting intelligence system. "
                "When given extraction results, call the graph_write_tool to persist them "
                "into the knowledge graph. Return the write statistics as-is. "
                "CRISPE Experiment Clause: Ensure that every contradiction/conflict flag has "
                "a confidence score and a 2-3 sentence reasoning trace attached to it. "
                "Escalate the contradiction flag to the team if the confidence score is below 0.6."
            ),
            tools=[graph_write_tool],
        )
        logger.info("Created ADK Graph Writer Agent: %s", AGENT_NAME)
        return agent
    except ImportError:
        logger.warning("google-adk not installed — Graph Writer ADK agent unavailable")
        return None


def create_graph_writer_a2a_app():
    """Create an A2A ASGI application for the Graph Writer Agent."""
    agent = create_graph_writer_adk_agent()
    if agent is None:
        raise RuntimeError("Cannot create A2A app: google-adk not available")
    try:
        from google.adk.a2a import to_a2a
        return to_a2a(agent)
    except ImportError:
        raise RuntimeError("google-adk[a2a] not installed")
