"""
Extraction Agent — Google ADK Agent + A2A Server + LangGraph internals.

Uses a minimal LangGraph state graph to wrap the existing
prompt → call_llm → parse_response → retry loop.

Decision 3 (from v2 plan): minimal LangGraph wrapper only — no multi-node
graph with separate extraction/conflict-detection/entity-resolution nodes.
The 4-meeting demo sequence producing identical output is what matters.

The ADK Agent is the external interface (A2A server with Agent Card).
LangGraph manages internal retry-with-state flow control.
MockExtractor is used in mock mode — LangGraph is not invoked.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Annotated, Any, TypedDict

logger = logging.getLogger(__name__)

AGENT_NAME = "extraction_agent"
AGENT_DESCRIPTION = (
    "Extracts structured facts from meeting transcripts. Identifies decisions, "
    "action items, entities, topics, supersessions, and conflicts. Uses Gemini "
    "via Google ADK with LangGraph for internal retry flow control."
)


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph State Schema
# ─────────────────────────────────────────────────────────────────────────────

class ExtractionState(TypedDict):
    """State passed between LangGraph nodes in the extraction flow."""
    meeting_id: str
    transcript_text: str
    meeting_title: str
    existing_decisions_json: str   # JSON array from graph MCP tool
    system_prompt: str
    user_prompt: str
    raw_llm_response: str
    parse_error: str
    result_json: str               # Final ExtractionResult JSON (on success)
    attempt: int
    max_retries: int
    done: bool


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph Nodes
# ─────────────────────────────────────────────────────────────────────────────

def _build_prompt_node(state: ExtractionState) -> dict[str, Any]:
    """Build system and user prompts from meeting data and existing decisions."""
    from threadline.extractor import _build_prompt, _SYSTEM_PROMPT
    from threadline.models import Decision, MeetingTranscript

    transcript = MeetingTranscript(
        id=state["meeting_id"],
        source_file=f"{state['meeting_id']}.txt",
        text=state["transcript_text"],
        meeting_title=state.get("meeting_title") or state["meeting_id"],
    )

    existing = []
    try:
        raw = json.loads(state.get("existing_decisions_json", "[]"))
        existing = [Decision.model_validate(d) for d in raw]
    except Exception:
        pass

    user_prompt = _build_prompt(transcript, existing)
    return {
        "user_prompt": user_prompt,
        "system_prompt": _SYSTEM_PROMPT,
    }


def _call_llm_node(state: ExtractionState) -> dict[str, Any]:
    """Call the LLM. Uses Gemini if key available, else raises for retry logic."""
    import os

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    try:
        if gemini_key:
            import re
            import google.generativeai as genai
            from threadline.extractor import _SYSTEM_PROMPT
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            full = f"{_SYSTEM_PROMPT}\n\n{state['user_prompt']}\n\nReturn only valid JSON."
            raw = model.generate_content(full).text or ""
            raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
            raw = re.sub(r"\s*```$", "", raw)
        elif openai_key:
            from openai import OpenAI
            from threadline.extractor import _SYSTEM_PROMPT
            client = OpenAI(api_key=openai_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": state["user_prompt"]},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            raw = resp.choices[0].message.content or ""
        else:
            raise ValueError(
                "No LLM API key available. Set GEMINI_API_KEY or OPENAI_API_KEY."
            )
        return {"raw_llm_response": raw, "parse_error": ""}
    except Exception as exc:
        return {"raw_llm_response": "", "parse_error": str(exc)}


def _parse_response_node(state: ExtractionState) -> dict[str, Any]:
    """Parse LLM response into ExtractionResult. Sets parse_error on failure."""
    from threadline.extractor import LLMExtractor
    from threadline.models import Decision, MeetingTranscript

    if not state["raw_llm_response"]:
        return {"parse_error": state.get("parse_error", "Empty LLM response")}

    existing = []
    try:
        raw = json.loads(state.get("existing_decisions_json", "[]"))
        existing = [Decision.model_validate(d) for d in raw]
    except Exception:
        pass

    extractor = LLMExtractor()
    try:
        result = extractor._parse(
            state["raw_llm_response"],
            state["meeting_id"],
            existing,
        )
        return {
            "result_json": result.model_dump_json(),
            "parse_error": "",
            "done": True,
        }
    except Exception as exc:
        return {"parse_error": str(exc), "done": False}


def _retry_or_fail_node(state: ExtractionState) -> dict[str, Any]:
    """Increment retry counter. If max reached, return empty result with error."""
    from threadline.models import ExtractionResult

    attempt = state.get("attempt", 0) + 1
    if attempt >= state.get("max_retries", 3):
        logger.error(
            "Extraction failed after %d attempts. Last error: %s",
            attempt, state.get("parse_error", "unknown"),
        )
        empty = ExtractionResult(
            meeting_id=state["meeting_id"],
            extraction_errors=[
                f"Extraction failed ({attempt} attempts): {state.get('parse_error', 'unknown')}"
            ],
        )
        return {"result_json": empty.model_dump_json(), "done": True, "attempt": attempt}

    delay = 1.0 * (2 ** (attempt - 1))
    logger.info("Retrying extraction in %.1fs (attempt %d)…", delay, attempt + 1)
    time.sleep(delay)
    return {"attempt": attempt, "done": False, "parse_error": ""}


def _should_retry(state: ExtractionState) -> str:
    """Routing function: go to END if done, else retry."""
    if state.get("done", False):
        return "done"
    return "retry"


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph Compilation
# ─────────────────────────────────────────────────────────────────────────────

def _build_extraction_graph():
    """
    Build and compile the LangGraph extraction state machine.

    Graph topology:
        START → build_prompt → call_llm → parse_response → [done | retry]
                                               ↑                     |
                                               └─────────────────────┘
    """
    from langgraph.graph import StateGraph, END

    graph = StateGraph(ExtractionState)

    graph.add_node("build_prompt", _build_prompt_node)
    graph.add_node("call_llm", _call_llm_node)
    graph.add_node("parse_response", _parse_response_node)
    graph.add_node("retry_or_fail", _retry_or_fail_node)

    graph.set_entry_point("build_prompt")
    graph.add_edge("build_prompt", "call_llm")
    graph.add_edge("call_llm", "parse_response")
    graph.add_conditional_edges(
        "parse_response",
        _should_retry,
        {"done": END, "retry": "retry_or_fail"},
    )
    graph.add_edge("retry_or_fail", "call_llm")

    return graph.compile()


# Cache the compiled graph (compiled once per process)
_extraction_graph = None


def _get_extraction_graph():
    global _extraction_graph
    if _extraction_graph is None:
        _extraction_graph = _build_extraction_graph()
    return _extraction_graph


# ─────────────────────────────────────────────────────────────────────────────
# ExtractionAgentRunner — direct in-process use
# ─────────────────────────────────────────────────────────────────────────────

class ExtractionAgentRunner:
    """
    Runs the LangGraph extraction flow. Used by both the ADK Agent tool
    and the Manager Agent's in-process fallback path.
    """

    def extract(
        self,
        meeting_id: str,
        transcript_text: str,
        meeting_title: str = "",
        existing_decisions_json: str = "[]",
        max_retries: int = 3,
    ) -> str:
        """
        Run the LangGraph extraction flow.

        Returns:
            JSON-serialized ExtractionResult.
        """
        graph = _get_extraction_graph()

        initial_state: ExtractionState = {
            "meeting_id": meeting_id,
            "transcript_text": transcript_text,
            "meeting_title": meeting_title or meeting_id,
            "existing_decisions_json": existing_decisions_json,
            "system_prompt": "",
            "user_prompt": "",
            "raw_llm_response": "",
            "parse_error": "",
            "result_json": "",
            "attempt": 0,
            "max_retries": max_retries,
            "done": False,
        }

        final_state = graph.invoke(initial_state)
        return final_state.get("result_json", "")


# ─────────────────────────────────────────────────────────────────────────────
# ADK Tool Function
# ─────────────────────────────────────────────────────────────────────────────

def extract_meeting_tool(
    meeting_id: str,
    transcript_text: str,
    meeting_title: str,
    existing_decisions_json: str,
) -> str:
    """
    ADK tool function: Extract structured facts from a meeting transcript.

    Runs the full LangGraph extraction pipeline:
    build_prompt → call_llm (Gemini/OpenAI) → parse_response → retry (up to 3×)

    Args:
        meeting_id: Unique meeting identifier.
        transcript_text: Full transcript text.
        meeting_title: Human-readable meeting title.
        existing_decisions_json: JSON array of prior decisions for context.

    Returns:
        JSON-serialized ExtractionResult.
    """
    runner = ExtractionAgentRunner()
    return runner.extract(
        meeting_id=meeting_id,
        transcript_text=transcript_text,
        meeting_title=meeting_title,
        existing_decisions_json=existing_decisions_json,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ADK Agent creation
# ─────────────────────────────────────────────────────────────────────────────

def create_extraction_adk_agent():
    """Create a Google ADK Extraction Agent backed by LangGraph."""
    try:
        from google.adk.agents import Agent

        agent = Agent(
            name=AGENT_NAME,
            model="gemini-2.0-flash",
            description=AGENT_DESCRIPTION,
            instruction=(
                "You are the Extraction Agent for the Threadline meeting intelligence system. "
                "When given a meeting transcript, call extract_meeting_tool to extract all "
                "structured facts: decisions, action items, entities, topics, supersessions, "
                "and conflicts. Return the extraction result JSON as-is without modification."
            ),
            tools=[extract_meeting_tool],
        )
        logger.info("Created ADK Extraction Agent: %s", AGENT_NAME)
        return agent
    except ImportError:
        logger.warning("google-adk not installed — Extraction ADK agent unavailable")
        return None


def create_extraction_a2a_app():
    """Create an A2A ASGI application for the Extraction Agent."""
    agent = create_extraction_adk_agent()
    if agent is None:
        raise RuntimeError("Cannot create A2A app: google-adk not available")
    try:
        from google.adk.a2a import to_a2a
        return to_a2a(agent)
    except ImportError:
        raise RuntimeError("google-adk[a2a] not installed")
