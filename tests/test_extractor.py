"""
Tests for threadline/extractor.py

Covers MockExtractor fixture responses, the under_review/superseded distinction,
and the create_extractor factory auto-degradation logic.
LLMExtractor tests are marked @pytest.mark.llm and skipped unless an API key is set.
"""
from __future__ import annotations

import os

import pytest

from threadline.extractor import MockExtractor, create_extractor
from threadline.models import (
    Decision,
    DecisionStatus,
    ExtractionResult,
    MeetingTranscript,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _transcript(meeting_id: str, text: str = "placeholder") -> MeetingTranscript:
    return MeetingTranscript(id=meeting_id, source_file=f"{meeting_id}.txt", text=text)


# ─────────────────────────────────────────────────────────────────────────────
# MockExtractor — meeting_01 (baseline)
# ─────────────────────────────────────────────────────────────────────────────

class TestMockExtractorMeeting01:
    def test_returns_extraction_result(self, mock_extractor):
        t = _transcript("meeting_01")
        r = mock_extractor.extract(t)
        assert isinstance(r, ExtractionResult)
        assert r.meeting_id == "meeting_01"

    def test_has_expected_decisions(self, mock_extractor):
        r = mock_extractor.extract(_transcript("meeting_01"))
        assert len(r.decisions) >= 4
        texts = [d.text for d in r.decisions]
        assert any("React" in t for t in texts)
        assert any("Auth0" in t for t in texts)
        assert any("PostgreSQL" in t for t in texts)

    def test_all_decisions_confirmed(self, mock_extractor):
        r = mock_extractor.extract(_transcript("meeting_01"))
        for d in r.decisions:
            assert d.status == DecisionStatus.confirmed, (
                f"Expected confirmed, got {d.status.value} for: {d.text}"
            )

    def test_no_prior_updates_in_first_meeting(self, mock_extractor):
        r = mock_extractor.extract(_transcript("meeting_01"))
        assert r.prior_decision_updates == []

    def test_has_action_items(self, mock_extractor):
        r = mock_extractor.extract(_transcript("meeting_01"))
        assert len(r.action_items) >= 1

    def test_has_facts_derived_from_decisions(self, mock_extractor):
        r = mock_extractor.extract(_transcript("meeting_01"))
        assert len(r.facts) >= len(r.decisions)

    def test_no_extraction_errors(self, mock_extractor):
        r = mock_extractor.extract(_transcript("meeting_01"))
        assert r.extraction_errors == []


# ─────────────────────────────────────────────────────────────────────────────
# MockExtractor — meeting_02 (supersession: Postgres → MongoDB)
# ─────────────────────────────────────────────────────────────────────────────

class TestMockExtractorMeeting02:
    @pytest.fixture
    def existing_from_01(self, mock_extractor):
        return mock_extractor.extract(_transcript("meeting_01")).decisions

    def test_has_supersession_update(self, mock_extractor, existing_from_01):
        r = mock_extractor.extract(_transcript("meeting_02"), existing_from_01)
        # Must have a PriorDecisionUpdate with new_status=superseded
        superseded_updates = [
            u for u in r.prior_decision_updates
            if u.new_status == DecisionStatus.superseded
        ]
        assert len(superseded_updates) == 1, (
            "Expected exactly one superseded update in meeting_02"
        )

    def test_superseded_update_references_postgres(self, mock_extractor, existing_from_01):
        r = mock_extractor.extract(_transcript("meeting_02"), existing_from_01)
        su = next(u for u in r.prior_decision_updates if u.new_status == DecisionStatus.superseded)
        assert "PostgreSQL" in su.decision_text

    def test_supersession_record_created(self, mock_extractor, existing_from_01):
        r = mock_extractor.extract(_transcript("meeting_02"), existing_from_01)
        assert len(r.supersessions) >= 1
        s = r.supersessions[0]
        assert "PostgreSQL" in s.old_text
        assert "MongoDB"    in s.new_text

    def test_new_decision_is_mongodb(self, mock_extractor):
        r = mock_extractor.extract(_transcript("meeting_02"))
        texts = [d.text for d in r.decisions]
        assert any("MongoDB" in t for t in texts)


# ─────────────────────────────────────────────────────────────────────────────
# MockExtractor — meeting_03 (under_review: Auth0 GDPR conflict)
# THE CRITICAL TEST: under_review ≠ superseded
# ─────────────────────────────────────────────────────────────────────────────

class TestMockExtractorMeeting03:
    @pytest.fixture
    def existing_decisions(self, mock_extractor):
        r01 = mock_extractor.extract(_transcript("meeting_01"))
        r02 = mock_extractor.extract(_transcript("meeting_02"), r01.decisions)
        # Combine into what the graph store would have
        all_d = {d.id: d for d in r01.decisions}
        for d in r02.decisions:
            all_d[d.id] = d
        return list(all_d.values())

    def test_no_new_confirmed_decisions(self, mock_extractor):
        """meeting_03 raises a concern; it must NOT confirm a replacement."""
        r = mock_extractor.extract(_transcript("meeting_03"))
        assert len(r.decisions) == 0, (
            "meeting_03 should have zero new confirmed decisions "
            "(Auth0 concern raised, no replacement chosen)"
        )

    def test_auth0_is_under_review_not_superseded(self, mock_extractor):
        """
        THE KEY ASSERTION: Auth0 goes to under_review, not superseded.
        This is what the entire under_review state exists for.
        """
        r = mock_extractor.extract(_transcript("meeting_03"))
        auth0_updates = [
            u for u in r.prior_decision_updates
            if "Auth0" in u.decision_text
        ]
        assert len(auth0_updates) == 1, (
            "Expected exactly one PriorDecisionUpdate for Auth0"
        )
        update = auth0_updates[0]
        assert update.new_status == DecisionStatus.under_review, (
            f"Auth0 should be 'under_review' after meeting_03, "
            f"got '{update.new_status.value}' instead. "
            "meeting_03 raises a concern but does NOT confirm a replacement — "
            "that happens in meeting_04."
        )
        assert update.new_status != DecisionStatus.superseded, (
            "Auth0 must NOT be marked as 'superseded' in meeting_03 — "
            "no replacement authentication provider was confirmed in this meeting."
        )

    def test_no_supersession_record_for_auth0(self, mock_extractor):
        """Supersession record should only appear when a new decision is confirmed."""
        r = mock_extractor.extract(_transcript("meeting_03"))
        auth0_supersessions = [
            s for s in r.supersessions
            if "Auth0" in s.old_text
        ]
        assert len(auth0_supersessions) == 0, (
            "No SupersessionRecord should be created in meeting_03 — "
            "Auth0 is only under review, not superseded"
        )

    def test_conflict_record_created(self, mock_extractor):
        """meeting_03 should create a ConflictRecord for the Auth0 GDPR issue."""
        r = mock_extractor.extract(_transcript("meeting_03"))
        assert len(r.new_conflicts) >= 1
        conflict = r.new_conflicts[0]
        assert conflict.resolved is False
        assert "Auth0" in conflict.fact_a_text or "Auth0" in conflict.description


# ─────────────────────────────────────────────────────────────────────────────
# MockExtractor — meeting_04 (supersession confirmed: Auth0 → Keycloak)
# ─────────────────────────────────────────────────────────────────────────────

class TestMockExtractorMeeting04:
    def test_auth0_is_superseded_in_meeting_04(self, mock_extractor):
        """After meeting_04, Auth0 must be superseded (not under_review anymore)."""
        r = mock_extractor.extract(_transcript("meeting_04"))
        auth0_updates = [
            u for u in r.prior_decision_updates
            if "Auth0" in u.decision_text
        ]
        assert len(auth0_updates) == 1
        update = auth0_updates[0]
        assert update.new_status == DecisionStatus.superseded, (
            f"Auth0 should be 'superseded' in meeting_04, "
            f"got '{update.new_status.value}'"
        )

    def test_new_keycloak_decision(self, mock_extractor):
        r = mock_extractor.extract(_transcript("meeting_04"))
        texts = [d.text for d in r.decisions]
        assert any("Keycloak" in t for t in texts)

    def test_supersession_record_created(self, mock_extractor):
        """Only when existing decisions are provided can the SupersessionRecord be built."""
        # Simulate that existing decisions include Auth0 (dec_m1_04)
        from threadline.extractor import _MOCK_RESPONSES
        existing = _MOCK_RESPONSES["meeting_01"]["decisions"]
        r = mock_extractor.extract(_transcript("meeting_04"), existing)
        auth0_sup = [s for s in r.supersessions if "Auth0" in s.old_text]
        assert len(auth0_sup) == 1

    def test_conflict_marked_resolved(self, mock_extractor):
        """meeting_04 should mark the Auth0 conflict as resolved."""
        r = mock_extractor.extract(_transcript("meeting_04"))
        resolved = [c for c in r.new_conflicts if c.resolved]
        assert len(resolved) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# MockExtractor — unknown meeting ID (generic fallback)
# ─────────────────────────────────────────────────────────────────────────────

class TestMockExtractorGeneric:
    def test_unknown_id_returns_result(self, mock_extractor):
        r = mock_extractor.extract(_transcript("some_random_meeting"))
        assert isinstance(r, ExtractionResult)
        assert r.meeting_id == "some_random_meeting"
        assert len(r.decisions) >= 1
        assert len(r.facts) >= 1

    def test_no_errors_on_unknown_id(self, mock_extractor):
        r = mock_extractor.extract(_transcript("unknown_mtg_999"))
        assert r.extraction_errors == []


# ─────────────────────────────────────────────────────────────────────────────
# create_extractor factory — auto-degradation
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateExtractor:
    def test_returns_mock_when_no_key(self):
        from threadline.config import Settings, ExtractorBackend
        s = Settings(extractor_backend=ExtractorBackend.openai, openai_api_key="")
        ext = create_extractor(s)
        assert isinstance(ext, MockExtractor)

    def test_returns_mock_when_explicit(self):
        from threadline.config import Settings, ExtractorBackend
        s = Settings(extractor_backend=ExtractorBackend.mock)
        ext = create_extractor(s)
        assert isinstance(ext, MockExtractor)

    @pytest.mark.llm
    def test_returns_llm_extractor_with_key(self):
        """Requires OPENAI_API_KEY to be set."""
        from threadline.config import Settings, ExtractorBackend
        from threadline.extractor import LLMExtractor
        key = os.getenv("OPENAI_API_KEY", "")
        if not key:
            pytest.skip("OPENAI_API_KEY not set")
        s = Settings(extractor_backend=ExtractorBackend.openai, openai_api_key=key)
        ext = create_extractor(s)
        assert isinstance(ext, LLMExtractor)
