"""
Agent Registry — A2A server lifecycle and store wiring.

Decision 4 (v2 plan): Single-process ASGI sub-mounts.
All agents run as ASGI sub-apps under the main FastAPI process.
No separate processes to start or monitor on demo day.

Also responsible for:
 - Wiring MCP singleton store references at startup
 - Exposing helper to get the ManagerAgentRunner for pipeline use
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Store wiring — called once at app startup
# ─────────────────────────────────────────────────────────────────────────────

def wire_stores(graph_store, vector_store) -> None:
    """
    Set the singleton store references used by MCP tool functions.
    Must be called before any agent tool is invoked.
    """
    from threadline.mcp.graph_mcp import set_graph_store
    from threadline.mcp.vector_mcp import set_vector_store

    set_graph_store(graph_store)
    set_vector_store(vector_store)
    logger.info("Agent registry: stores wired (%s / %s)",
                type(graph_store).__name__, type(vector_store).__name__)


# ─────────────────────────────────────────────────────────────────────────────
# A2A App mounts — sub-apps for each agent
# ─────────────────────────────────────────────────────────────────────────────

def build_a2a_mounts() -> dict[str, Any]:
    """
    Build ASGI sub-apps for each ADK agent and return a dict of
    {mount_path: asgi_app} for registration with the FastAPI main app.

    Each mount exposes:
      - POST /<agent>/run     — invoke agent
      - GET  /<agent>/.well-known/agent-card.json — agent discovery

    Returns empty dict if google-adk[a2a] is not installed (graceful).
    """
    mounts: dict[str, Any] = {}
    import os
    if os.environ.get("THREADLINE_TESTING") == "1":
        logger.info("Test environment detected: skipping A2A app mounts to prevent GCP auth timeouts.")
        return mounts

    try:
        from google.adk.a2a import to_a2a
    except ImportError:
        logger.warning(
            "google-adk[a2a] not installed — A2A mounts unavailable. "
            "Pipeline will run in in-process mode."
        )
        return mounts

    # Briefing Agent
    try:
        from threadline.agents.briefing_agent import create_briefing_adk_agent
        agent = create_briefing_adk_agent()
        if agent:
            mounts["/a2a/briefing"] = to_a2a(agent)
            logger.info("A2A mount registered: /a2a/briefing")
    except Exception as exc:
        logger.warning("Failed to mount Briefing A2A agent: %s", exc)

    # Graph Writer Agent
    try:
        from threadline.agents.graph_writer_agent import create_graph_writer_adk_agent
        agent = create_graph_writer_adk_agent()
        if agent:
            mounts["/a2a/graph-writer"] = to_a2a(agent)
            logger.info("A2A mount registered: /a2a/graph-writer")
    except Exception as exc:
        logger.warning("Failed to mount Graph Writer A2A agent: %s", exc)

    # Semantic Memory Agent
    try:
        from threadline.agents.semantic_memory_agent import create_semantic_memory_adk_agent
        agent = create_semantic_memory_adk_agent()
        if agent:
            mounts["/a2a/semantic-memory"] = to_a2a(agent)
            logger.info("A2A mount registered: /a2a/semantic-memory")
    except Exception as exc:
        logger.warning("Failed to mount Semantic Memory A2A agent: %s", exc)

    # Extraction Agent
    try:
        from threadline.agents.extraction_agent import create_extraction_adk_agent
        agent = create_extraction_adk_agent()
        if agent:
            mounts["/a2a/extraction"] = to_a2a(agent)
            logger.info("A2A mount registered: /a2a/extraction")
    except Exception as exc:
        logger.warning("Failed to mount Extraction A2A agent: %s", exc)

    # Input Agent
    try:
        from threadline.agents.input_agent import create_input_adk_agent
        agent = create_input_adk_agent()
        if agent:
            mounts["/a2a/input"] = to_a2a(agent)
            logger.info("A2A mount registered: /a2a/input")
    except Exception as exc:
        logger.warning("Failed to mount Input A2A agent: %s", exc)

    # Manager Agent
    try:
        from threadline.agents.manager_agent import create_manager_adk_agent
        agent = create_manager_adk_agent()
        if agent:
            mounts["/a2a/manager"] = to_a2a(agent)
            logger.info("A2A mount registered: /a2a/manager")
    except Exception as exc:
        logger.warning("Failed to mount Manager A2A agent: %s", exc)

    logger.info("Agent registry: %d A2A mounts ready", len(mounts))
    return mounts


# ─────────────────────────────────────────────────────────────────────────────
# Manager runner accessor
# ─────────────────────────────────────────────────────────────────────────────

def get_manager_runner():
    """Return a ManagerAgentRunner instance for pipeline use."""
    from threadline.agents.manager_agent import ManagerAgentRunner
    return ManagerAgentRunner()


# ─────────────────────────────────────────────────────────────────────────────
# Agent Card listing — for /api/v1/agents endpoint
# ─────────────────────────────────────────────────────────────────────────────

def list_agent_cards() -> list[dict]:
    """Return metadata about all registered agents."""
    agents = [
        {
            "name": "input_agent",
            "description": "Handles meeting file ingestion and audio transcription (Gemini / Whisper).",
            "a2a_path": "/a2a/input",
        },
        {
            "name": "extraction_agent",
            "description": "Extracts decisions, actions, entities, conflicts (ADK + LangGraph).",
            "a2a_path": "/a2a/extraction",
        },
        {
            "name": "graph_writer_agent",
            "description": "Persists extraction results into the Neo4j knowledge graph via MCP tools.",
            "a2a_path": "/a2a/graph-writer",
        },
        {
            "name": "semantic_memory_agent",
            "description": "Indexes facts into the Qdrant vector store via MCP tools.",
            "a2a_path": "/a2a/semantic-memory",
        },
        {
            "name": "briefing_agent",
            "description": "Generates executive Markdown briefing from all meeting data.",
            "a2a_path": "/a2a/briefing",
        },
        {
            "name": "manager_agent",
            "description": "Orchestrator: delegates to all agents. Lyzr Studio primary, ADK fallback.",
            "a2a_path": "/a2a/manager",
        },
    ]
    return agents
