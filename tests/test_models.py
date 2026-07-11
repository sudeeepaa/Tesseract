"""
Tests for threadline/models.py

Covers: serialization round-trips, DecisionStatus state machine,
Decision.is_active(), ExtractionResult construction.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from threadline.models import (
    ActionItem,
    ActionItemStatus,
    BriefingOutput,
    ConflictRecord,
    Decision,
    DecisionStatus,
    EntityType,
    ExtractionResult,
    ExtractedFact,
    FactType,
    GraphEdge,
    GraphNode,
    GraphSnapshot,
    MeetingTranscript,
    NodeType,
    EdgeType,
    PipelineStage,
    PipelineResult,
    PriorDecisionUpdate,
    SearchResult,
    StageEvent,
    StageStatus,
    SupersessionRecord,
    Topic,
)


# ─────────────────────────────────────────────────────────────────────────────
# DecisionStatus
# ─────────────────────────────────────────────────────────────────────────────

class TestDecisionStatus:
    def test_all_five_values_exist(self):
        assert set(DecisionStatus) == {
            DecisionStatus.proposed,
            DecisionStatus.confirmed,
            DecisionStatus.under_review,
            DecisionStatus.superseded,
            DecisionStatus.reversed,
        }

    def test_string_values(self):
        assert DecisionStatus.under_review.value == "under_review"
        assert DecisionStatus.superseded.value   == "superseded"

    def test_under_review_is_not_superseded(self):
        """Critical: these must be distinct values."""
        assert DecisionStatus.under_review != DecisionStatus.superseded

    def test_parse_from_string(self):
        assert DecisionStatus("under_review") == DecisionStatus.under_review
        assert DecisionStatus("superseded")   == DecisionStatus.superseded

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError):
            DecisionStatus("invalid_status")


# ─────────────────────────────────────────────────────────────────────────────
# Decision
# ─────────────────────────────────────────────────────────────────────────────

class TestDecision:
    def test_default_status_is_confirmed(self):
        d = Decision(text="Use React", source_meeting_id="m1")
        assert d.status == DecisionStatus.confirmed

    def test_is_active_confirmed(self):
        d = Decision(text="Use React", status=DecisionStatus.confirmed, source_meeting_id="m1")
        assert d.is_active() is True

    def test_is_active_proposed(self):
        d = Decision(text="Use React", status=DecisionStatus.proposed, source_meeting_id="m1")
        assert d.is_active() is True

    def test_is_active_under_review(self):
        """Under-review decisions are still active (not yet replaced)."""
        d = Decision(text="Use Auth0", status=DecisionStatus.under_review, source_meeting_id="m1")
        assert d.is_active() is True

    def test_is_active_superseded(self):
        d = Decision(text="Use Postgres", status=DecisionStatus.superseded, source_meeting_id="m1")
        assert d.is_active() is False

    def test_is_active_reversed(self):
        d = Decision(text="Use Postgres", status=DecisionStatus.reversed, source_meeting_id="m1")
        assert d.is_active() is False

    def test_serialization_round_trip(self):
        d = Decision(
            id="abc12345",
            text="Use Auth0 for authentication",
            status=DecisionStatus.under_review,
            owner="Dev Rao",
            source_meeting_id="meeting_03",
        )
        data     = d.model_dump()
        restored = Decision.model_validate(data)
        assert restored.id     == d.id
        assert restored.text   == d.text
        assert restored.status == DecisionStatus.under_review
        assert restored.owner  == d.owner

    def test_json_round_trip(self):
        d    = Decision(text="Test decision", source_meeting_id="m1")
        raw  = d.model_dump_json()
        back = Decision.model_validate_json(raw)
        assert back.text   == d.text
        assert back.status == d.status


# ─────────────────────────────────────────────────────────────────────────────
# PriorDecisionUpdate
# ─────────────────────────────────────────────────────────────────────────────

class TestPriorDecisionUpdate:
    def test_under_review_update(self):
        """meeting_03 scenario: Auth0 flagged, no replacement yet."""
        pu = PriorDecisionUpdate(
            decision_id="dec_m1_04",
            decision_text="Use Auth0 for authentication",
            new_status=DecisionStatus.under_review,
            reason="GDPR carve-outs in standard tier",
        )
        assert pu.new_status == DecisionStatus.under_review
        assert pu.new_decision_id is None

    def test_superseded_update_has_new_decision_id(self):
        """meeting_04 scenario: Auth0 replaced by Keycloak."""
        pu = PriorDecisionUpdate(
            decision_id="dec_m1_04",
            decision_text="Use Auth0 for authentication",
            new_status=DecisionStatus.superseded,
            reason="Keycloak selected by Marcus",
            new_decision_id="dec_m4_01",
        )
        assert pu.new_status      == DecisionStatus.superseded
        assert pu.new_decision_id == "dec_m4_01"


# ─────────────────────────────────────────────────────────────────────────────
# ExtractionResult
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractionResult:
    def test_empty_result(self):
        r = ExtractionResult(meeting_id="m1")
        assert r.decisions     == []
        assert r.action_items  == []
        assert r.new_conflicts == []
        assert r.supersessions == []
        assert r.extraction_errors == []

    def test_with_decisions(self):
        d = Decision(text="Use React", source_meeting_id="m1")
        r = ExtractionResult(meeting_id="m1", decisions=[d])
        assert len(r.decisions) == 1
        assert r.decisions[0].text == "Use React"

    def test_serialization(self):
        d  = Decision(text="Use React", source_meeting_id="m1")
        ai = ActionItem(text="Write tests", source_meeting_id="m1")
        r  = ExtractionResult(meeting_id="m1", decisions=[d], action_items=[ai])
        raw  = r.model_dump_json()
        back = ExtractionResult.model_validate_json(raw)
        assert len(back.decisions)    == 1
        assert len(back.action_items) == 1
        assert back.meeting_id        == "m1"


# ─────────────────────────────────────────────────────────────────────────────
# StageEvent / PipelineResult
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineModels:
    def test_stage_event(self):
        ev = StageEvent(
            stage=PipelineStage.EXTRACT,
            status=StageStatus.done,
            message="5 decisions extracted",
            data={"decisions": 5},
        )
        assert ev.stage   == PipelineStage.EXTRACT
        assert ev.status  == StageStatus.done
        assert ev.data    == {"decisions": 5}

    def test_pipeline_result_defaults(self):
        r = PipelineResult(meeting_id="m1")
        assert r.overall_success  is True
        assert r.graph_success    is False
        assert r.vector_success   is False
        assert r.briefing_success is False
        assert r.errors           == []


# ─────────────────────────────────────────────────────────────────────────────
# GraphSnapshot
# ─────────────────────────────────────────────────────────────────────────────

class TestGraphSnapshot:
    def test_empty_snapshot(self):
        snap = GraphSnapshot()
        assert snap.nodes == []
        assert snap.edges == []
        assert snap.generated_at is not None

    def test_with_nodes_and_edges(self):
        n = GraphNode(id="d1", label="Use React", type=NodeType.decision)
        e = GraphEdge(source="d2", target="d1", type=EdgeType.supersedes, superseded=True)
        snap = GraphSnapshot(nodes=[n], edges=[e])
        assert len(snap.nodes)          == 1
        assert len(snap.edges)          == 1
        assert snap.edges[0].superseded is True


# ─────────────────────────────────────────────────────────────────────────────
# SearchResult
# ─────────────────────────────────────────────────────────────────────────────

class TestSearchResult:
    def test_score_clamped(self):
        sr = SearchResult(
            fact_id="f1", text="Some fact",
            score=0.87, meeting_id="m1",
        )
        assert 0.0 <= sr.score <= 1.0

    def test_invalid_score_raises(self):
        with pytest.raises(Exception):
            SearchResult(fact_id="f1", text="x", score=1.5, meeting_id="m1")
