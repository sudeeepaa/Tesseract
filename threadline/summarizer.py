"""
Answer synthesis for the "Ask your meetings" feature (retrieval-augmented).

Takes the user's natural-language question plus the semantic-search hits and asks
the configured LLM (Gemini or OpenAI) to write a short, grounded answer. This is
deliberately separate from the extraction path — it produces prose, not the
extraction JSON, so it never routes through the Lyzr extraction agent.

Graceful degradation: with no LLM key (mock mode) it returns ``None`` and the UI
simply shows the matching facts, exactly as before.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional, Tuple

from threadline.models import ActionItem, Decision, SearchResult

logger = logging.getLogger(__name__)

_ANSWER_SYSTEM = (
    "You are Tesseract, an AI chief of staff searching a set of meeting records. "
    "Using ONLY the meeting facts provided below — never outside knowledge — answer the "
    "user's question in 2-4 concise sentences of plain business language, citing the "
    "relevant decision or meeting when it helps.\n"
    "Also judge whether those facts actually address the question. Respond with ONLY a "
    'JSON object: {"grounded": true|false, "answer": "..."}.\n'
    "Set \"grounded\" to false when the meetings do not really cover the question (an "
    "off-topic or unanswerable query, e.g. general trivia). When it is false, make "
    "\"answer\" a short note that the meetings don't cover this — do NOT describe yourself."
)


def _build_prompt(query: str, results: list[SearchResult]) -> str:
    lines = []
    for r in results:
        ftype = getattr(r.fact_type, "value", str(r.fact_type))
        speaker = f", {r.speaker}" if r.speaker else ""
        lines.append(f"- ({ftype} · {r.meeting_id}{speaker}) {r.text}")
    facts = "\n".join(lines) if lines else "(no matching facts)"
    return f"QUESTION:\n{query}\n\nMEETING FACTS:\n{facts}\n\nJSON:"


def _parse_answer(raw: str) -> Tuple[Optional[str], bool]:
    """Parse the {grounded, answer} JSON; fall back to raw text if it isn't JSON."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip())
    try:
        obj = json.loads(cleaned)
        answer = (obj.get("answer") or "").strip() or None
        grounded = bool(obj.get("grounded", True))
        return answer, grounded
    except Exception:
        # Not JSON — treat the whole thing as the answer and assume grounded.
        return (raw or "").strip() or None, True


def summarize_answer(
    query: str,
    results: list[SearchResult],
    settings,
) -> Tuple[Optional[str], bool]:
    """
    Synthesize a grounded natural-language answer from search hits.

    Returns ``(answer, grounded)``. ``grounded`` is False when the meetings don't
    actually cover the question, so callers can suppress the (weak) match list.
    When no LLM backend is available, returns ``(None, True)`` so the UI shows the
    raw results exactly as before.
    """
    if not query.strip() or not results:
        return None, False

    backend = settings.effective_extractor_backend.value
    prompt = _build_prompt(query, results)

    try:
        if backend == "gemini" and settings.gemini_api_key:
            import google.generativeai as genai
            genai.configure(api_key=settings.gemini_api_key)
            model = genai.GenerativeModel(settings.gemini_model)
            resp = model.generate_content(
                f"{_ANSWER_SYSTEM}\n\n{prompt}",
                request_options={"timeout": 30},
            )
            return _parse_answer(resp.text or "")

        if backend == "openai" and settings.openai_api_key:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            resp = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": _ANSWER_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            return _parse_answer(resp.choices[0].message.content or "")

        # mock / no key → no synthesized answer; UI shows raw results.
        return None, True

    except Exception as exc:
        logger.warning("Search answer synthesis failed (%s) — returning results only", exc)
        return None, True


# ── Per-meeting summary (for the meetings dashboard) ──────────────────────────

_MEETING_SYSTEM = (
    "You are Tesseract, an AI chief of staff. Write a crisp executive summary of a "
    "single meeting for a non-technical stakeholder, using ONLY the structured facts "
    "provided. Use short markdown: a one-paragraph overview, then a '**Decisions**' "
    "bullet list and an '**Action items**' bullet list (owner in parentheses). Omit a "
    "section if it has no items. Be factual and concise — do not invent anything."
)


def _fallback_meeting_summary(title, decisions, action_items, topics) -> str:
    """Deterministic markdown summary used when no LLM is available."""
    lines = [f"# {title}", ""]
    if topics:
        lines.append("_Topics: " + ", ".join(topics) + "_")
        lines.append("")
    if decisions:
        lines.append("**Decisions**")
        for d in decisions:
            owner = f" ({d.owner})" if d.owner else ""
            lines.append(f"- {d.text} — _{d.status.value}_{owner}")
        lines.append("")
    if action_items:
        lines.append("**Action items**")
        for a in action_items:
            who = f" ({a.assignee})" if a.assignee else ""
            lines.append(f"- {a.text}{who}")
        lines.append("")
    if not decisions and not action_items:
        lines.append("_No decisions or action items were captured for this meeting._")
    return "\n".join(lines).strip()


def summarize_meeting(
    title: str,
    decisions: list[Decision],
    action_items: list[ActionItem],
    topics: list[str],
    settings,
) -> str:
    """
    Produce a markdown summary of one meeting. Uses the configured LLM when
    available, otherwise a deterministic structured fallback (so the feature — and
    its download — always works, even in mock mode).
    """
    dec_block = "\n".join(
        f"- {d.text} [status: {d.status.value}"
        + (f", owner: {d.owner}" if d.owner else "")
        + (f", rationale: {d.rationale}" if d.rationale else "")
        + "]"
        for d in decisions
    ) or "(none)"
    ai_block = "\n".join(
        f"- {a.text}" + (f" (assignee: {a.assignee})" if a.assignee else "")
        for a in action_items
    ) or "(none)"
    topic_block = ", ".join(topics) or "(none)"
    prompt = (
        f"MEETING: {title}\n\n"
        f"DECISIONS:\n{dec_block}\n\n"
        f"ACTION ITEMS:\n{ai_block}\n\n"
        f"TOPICS: {topic_block}\n\nSUMMARY (markdown):"
    )

    backend = settings.effective_extractor_backend.value
    try:
        if backend == "gemini" and settings.gemini_api_key:
            import google.generativeai as genai
            genai.configure(api_key=settings.gemini_api_key)
            model = genai.GenerativeModel(settings.gemini_model)
            resp = model.generate_content(
                f"{_MEETING_SYSTEM}\n\n{prompt}", request_options={"timeout": 30}
            )
            text = (resp.text or "").strip()
            if text:
                return text
        elif backend == "openai" and settings.openai_api_key:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            resp = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": _MEETING_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                return text
    except Exception as exc:
        logger.warning("Meeting summary LLM call failed (%s) — using fallback", exc)

    return _fallback_meeting_summary(title, decisions, action_items, topics)
