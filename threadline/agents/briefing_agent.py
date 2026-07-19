"""
Briefing Agent — Google ADK Agent + A2A Server.

Wraps the existing BriefingGenerator as a real ADK Agent that can be
exposed as an A2A server with its own Agent Card. Uses MCP tools
(graph_mcp) to fetch data from the knowledge graph.

This is the simplest agent in the system: no LLM call, pure template
rendering. It receives a task request, queries the graph via MCP tools,
and returns a BriefingOutput.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from threadline.briefing import BriefingGenerator
from threadline.models import (
    ActionItem,
    BriefingOutput,
    ConflictRecord,
    Decision,
)
from threadline.mcp.graph_mcp import (
    graph_get_all_decisions,
    graph_get_all_action_items,
    graph_get_all_conflicts,
    graph_get_all_topics,
    graph_get_meeting_count,
)

logger = logging.getLogger(__name__)

# Agent metadata for the A2A Agent Card
AGENT_NAME = "briefing_agent"
AGENT_DESCRIPTION = (
    "Generates an executive briefing from meeting intelligence data. "
    "Queries the knowledge graph for all decisions, action items, conflicts, "
    "and topics, then renders a structured Markdown briefing with status tracking."
)


class BriefingAgentRunner:
    """
    Encapsulates the Briefing Agent's logic. Can be used directly
    (for in-process testing) or wrapped by the ADK Agent framework
    for A2A server exposure.

    The runner uses MCP tool functions to access the graph store,
    not direct Python store references.
    """

    def __init__(self) -> None:
        self._generator = BriefingGenerator()

    def generate_briefing(self) -> BriefingOutput:
        """
        Generate a briefing by querying the graph via MCP tools.

        Returns:
            BriefingOutput with structured data and Markdown.
        """
        # Fetch all data via MCP tools (returns JSON strings)
        decisions_raw = json.loads(graph_get_all_decisions())
        action_items_raw = json.loads(graph_get_all_action_items())
        conflicts_raw = json.loads(graph_get_all_conflicts())
        topics = json.loads(graph_get_all_topics())
        meeting_count_raw = json.loads(graph_get_meeting_count())

        # Deserialize into Pydantic models
        all_decisions = [Decision.model_validate(d) for d in decisions_raw]
        all_action_items = [ActionItem.model_validate(ai) for ai in action_items_raw]
        all_conflicts = [ConflictRecord.model_validate(c) for c in conflicts_raw]
        meeting_count = meeting_count_raw["count"]

        # Detect staleness of action items per PRD §12.5
        from datetime import datetime
        from threadline.models import ActionItemStatus

        meetings_processed = sorted(list(set(ai.source_meeting_id for ai in all_action_items)))
        latest_meeting_id = meetings_processed[-1] if meetings_processed else None

        for ai in all_action_items:
            if ai.status in (ActionItemStatus.open, ActionItemStatus.in_progress):
                is_past_due = False
                if ai.due_date:
                    try:
                        due_dt = datetime.strptime(ai.due_date, "%Y-%m-%d")
                        if due_dt.date() < datetime.now().date():
                            is_past_due = True
                    except Exception:
                        is_past_due = True

                is_older_meeting = latest_meeting_id and ai.source_meeting_id != latest_meeting_id

                if is_past_due or is_older_meeting:
                    ai.is_stale = True
                    ai.confidence = 0.95
                    ai.reasoning = (
                        f"Action item has remained open since {ai.source_meeting_id} with due date {ai.due_date}. "
                        f"This exceeds standard 1-meeting review threshold cycles, suggesting workflow stagnation. "
                        f"Re-assign or resolve immediately."
                    )

        # Delegate to existing BriefingGenerator
        return self._generator.generate(
            all_decisions=all_decisions,
            all_action_items=all_action_items,
            all_conflicts=all_conflicts,
            all_topics=topics,
            meeting_count=meeting_count,
        )


def generate_briefing_tool() -> str:
    """
    ADK tool function: Generate an executive briefing from all meeting data.

    Queries the knowledge graph for decisions, action items, conflicts,
    and topics, then renders a structured Markdown briefing.

    Returns:
        JSON-serialized BriefingOutput.
    """
    runner = BriefingAgentRunner()
    briefing = runner.generate_briefing()
    return briefing.model_dump_json()


# ─────────────────────────────────────────────────────────────────────────────
# ADK Agent creation
# ─────────────────────────────────────────────────────────────────────────────

def create_briefing_adk_agent():
    """
    Create and return a Google ADK Agent for briefing generation.

    The agent is configured with:
    - System instructions for briefing rendering
    - MCP tools for graph queries
    - generate_briefing_tool as its primary action

    Returns:
        A google.adk.Agent instance ready for A2A exposure.
    """
    try:
        from google.adk.agents import Agent

        agent = Agent(
            name=AGENT_NAME,
            model="gemini-2.0-flash",
            description=AGENT_DESCRIPTION,
            instruction=(
                "You are the Briefing Agent for the Tesseract meeting intelligence system. "
                "When asked to generate a briefing, call the generate_briefing_tool to produce "
                "an executive briefing from all meeting data in the knowledge graph. "
                "Return the briefing output as-is — do not modify or summarize it. "
                "CRISPE Experiment Clause: Ensure that every stale-item flag has "
                "a confidence score and a 2-3 sentence reasoning trace attached to it. "
                "Escalate the stale-item flag to the team if the confidence score is below 0.6."
            ),
            tools=[generate_briefing_tool],
        )
        logger.info("Created ADK Briefing Agent: %s", AGENT_NAME)
        return agent

    except ImportError:
        logger.warning(
            "google-adk not installed. BriefingAgentRunner is available "
            "but ADK Agent wrapper cannot be created."
        )
        return None


def create_briefing_a2a_app():
    """
    Create an A2A ASGI application for the Briefing Agent.

    Returns:
        An ASGI app (Starlette/FastAPI) that serves the A2A protocol
        endpoints including the Agent Card.
    """
    agent = create_briefing_adk_agent()
    if agent is None:
        raise RuntimeError("Cannot create A2A app: google-adk not available")

    try:
        from google.adk.a2a import to_a2a

        a2a_app = to_a2a(agent)
        logger.info("Briefing Agent A2A server created")
        return a2a_app

    except ImportError:
        raise RuntimeError(
            "Cannot create A2A app: google-adk[a2a] not installed. "
            "Install with: pip install 'google-adk[a2a]'"
        )
