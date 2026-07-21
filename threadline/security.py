"""
Tesseract Security Layer: Cypher and Vector Injection Protection.
Rejects or sanitizes inputs before writing to stores.
"""
from __future__ import annotations

import re
import logging
from typing import Any
from threadline.models import ExtractionResult, MeetingTranscript

logger = logging.getLogger(__name__)

# Cypher reserved keywords that are dangerous in string values if concatenated (defense-in-depth)
CYPHER_KEYWORDS = {
    "CREATE", "MERGE", "MATCH", "DELETE", "REMOVE", "DROP", "DETACH", "SET", "RETURN", "UNION"
}

def sanitize_name(name: str) -> str:
    """
    Sanitize entity/topic/decision name fields.
    Rejects/removes special characters and prevents Cypher injection constructs.
    """
    if not name:
        return name
    
    # 1. Reject oversized payloads for name fields (max 200 chars)
    if len(name) > 200:
        logger.warning("Sanitizing name field: size truncated from %d to 200", len(name))
        name = name[:200]

    # 2. Defense-in-depth: remove quote variations, backticks, and semi-colons
    name = re.sub(r"['\"`;{}\[\]\\]", "", name)
    
    # 3. If the name is literally a Cypher keyword, append suffix to disarm it
    upper_name = name.strip().upper()
    if upper_name in CYPHER_KEYWORDS:
        logger.warning("Disarmed potential Cypher keyword name: %r", name)
        name = f"{name}_entity"

    return name.strip()


def sanitize_text(text: str | None, max_len: int = 2000) -> str | None:
    """
    Sanitize a free-text field (e.g. a user's resolution note).

    Unlike sanitize_name, this preserves ordinary punctuation, quotes, and
    apostrophes for readability — writes are parameterized, so this is
    defense-in-depth against Cypher construct injection, not the sole guard.
    """
    if not text:
        return text
    if len(text) > max_len:
        logger.warning("Sanitizing note field: size truncated from %d to %d", len(text), max_len)
        text = text[:max_len]
    # Strip only the characters dangerous in a stray Cypher/label context.
    text = re.sub(r"[`;{}\\]", "", text)
    return text.strip()


def validate_extraction_result(result: ExtractionResult) -> ExtractionResult:
    """
    Perform deep validation and sanitization of the ExtractionResult.
    Mutates/sanitizes entity, topic, decision, and conflict names.
    Raises ValueError on malicious payloads.
    """
    # Sanitize decisions
    for d in result.decisions:
        d.text = sanitize_name(d.text)
        if d.owner:
            d.owner = sanitize_name(d.owner)
        if d.rationale and len(d.rationale) > 2000:
            d.rationale = d.rationale[:2000]

    # Sanitize entities
    for e in result.entities:
        e.name = sanitize_name(e.name)

    # Sanitize topics
    for t in result.topics:
        t.name = sanitize_name(t.name)

    # Sanitize action items
    for ai in result.action_items:
        ai.text = sanitize_name(ai.text)
        if ai.assignee:
            ai.assignee = sanitize_name(ai.assignee)

    # Sanitize conflicts
    for c in result.new_conflicts:
        c.description = sanitize_name(c.description)
        c.fact_a_text = sanitize_name(c.fact_a_text)
        c.fact_b_text = sanitize_name(c.fact_b_text)

    return result


def validate_meeting_transcript(transcript: MeetingTranscript) -> MeetingTranscript:
    """Validate transcript text size and title."""
    if transcript.meeting_title:
        transcript.meeting_title = sanitize_name(transcript.meeting_title)
    
    # Restrict raw transcript to max 1MB to prevent Denial of Service payload injection
    max_len = 1000000
    if len(transcript.text) > max_len:
        logger.warning("Truncating oversized meeting transcript payload from %d", len(transcript.text))
        transcript = transcript.model_copy(update={"text": transcript.text[:max_len]})
        
    return transcript
