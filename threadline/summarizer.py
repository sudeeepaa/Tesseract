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

import logging
from typing import Optional

from threadline.models import SearchResult

logger = logging.getLogger(__name__)

_ANSWER_SYSTEM = (
    "You are Tesseract, an AI chief of staff. Answer the user's question using ONLY "
    "the meeting facts provided below — do not invent anything. Reply in 2-4 concise "
    "sentences of plain business language, and mention the relevant decision or meeting "
    "when it helps. If the facts don't actually answer the question, say so plainly "
    "instead of guessing."
)


def _build_prompt(query: str, results: list[SearchResult]) -> str:
    lines = []
    for r in results:
        ftype = getattr(r.fact_type, "value", str(r.fact_type))
        speaker = f", {r.speaker}" if r.speaker else ""
        lines.append(f"- ({ftype} · {r.meeting_id}{speaker}) {r.text}")
    facts = "\n".join(lines) if lines else "(no matching facts)"
    return f"QUESTION:\n{query}\n\nRELEVANT MEETING FACTS:\n{facts}\n\nANSWER:"


def summarize_answer(
    query: str,
    results: list[SearchResult],
    settings,
) -> Optional[str]:
    """
    Synthesize a grounded natural-language answer from search hits.

    Returns the answer text, or ``None`` when there's nothing to summarize or no
    LLM backend is available (so callers can fall back to showing raw results).
    """
    if not query.strip() or not results:
        return None

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
            return (resp.text or "").strip() or None

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
            )
            return (resp.choices[0].message.content or "").strip() or None

        # mock / no key → no synthesized answer, UI shows raw results.
        return None

    except Exception as exc:
        logger.warning("Search answer synthesis failed (%s) — returning results only", exc)
        return None
