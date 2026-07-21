"""
Tests for HybridExtractor routing (extractor.py).

The four canned demo fixtures (meeting_01..04) must ALWAYS resolve through the
deterministic MockExtractor so the flagship supersession/conflict narrative stays
reproducible — even when a real LLM backend is configured. Every other transcript
must be routed to the wrapped LLM extractor.
"""
from __future__ import annotations

from threadline.extractor import HybridExtractor
from threadline.models import ExtractionResult, MeetingTranscript


class _SpyLLM:
    """Stand-in LLM extractor that records calls and returns a sentinel."""

    def __init__(self):
        self.called_with: list[str] = []

    def extract(self, transcript, existing_decisions=None):
        self.called_with.append(transcript.id)
        return ExtractionResult(meeting_id=transcript.id, extraction_errors=["from-llm"])


def _t(meeting_id: str) -> MeetingTranscript:
    return MeetingTranscript(
        id=meeting_id, source_file=f"{meeting_id}.txt",
        text="Some transcript text.", meeting_title=meeting_id,
    )


def test_fixture_routes_to_mock_not_llm():
    spy = _SpyLLM()
    hybrid = HybridExtractor(spy)

    result = hybrid.extract(_t("meeting_01"))

    # Deterministic mock produced real decisions; the LLM was never touched.
    assert spy.called_with == []
    assert result.meeting_id == "meeting_01"
    assert result.decisions, "fixture should yield the canned mock decisions"
    assert any(d.id == "dec_m1_04" for d in result.decisions)


def test_non_fixture_routes_to_llm():
    spy = _SpyLLM()
    hybrid = HybridExtractor(spy)

    result = hybrid.extract(_t("acme_standup_2026_07"))

    assert spy.called_with == ["acme_standup_2026_07"]
    assert result.extraction_errors == ["from-llm"]
