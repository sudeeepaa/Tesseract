"""
Shared pytest fixtures for the Threadline test suite.

All fixtures use in-memory backends — no Docker, no API keys required.
Integration fixtures (Neo4j, Qdrant) are skipped unless THREADLINE_INTEGRATION=1.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from threadline.extractor    import MockExtractor
from threadline.graph_store  import InMemoryGraphStore
from threadline.vector_store import InMemoryVectorStore
from threadline.briefing     import BriefingGenerator
from threadline.pipeline     import Pipeline
from threadline.models       import MeetingTranscript

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ─────────────────────────────────────────────────────────────────────────────
# Store fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def graph_store() -> InMemoryGraphStore:
    """Fresh InMemoryGraphStore per test."""
    return InMemoryGraphStore()


@pytest.fixture
def vector_store() -> InMemoryVectorStore:
    """
    InMemoryVectorStore using hash-based embeddings (no model download).
    Force hash fallback so tests run fast in CI.
    """
    store = InMemoryVectorStore(embedding_model="all-MiniLM-L6-v2", embedding_dim=384)
    store._use_hash_embed = True   # skip model load in unit tests
    return store


@pytest.fixture
def mock_extractor() -> MockExtractor:
    return MockExtractor()


@pytest.fixture
def briefing_gen() -> BriefingGenerator:
    return BriefingGenerator()


@pytest.fixture
def pipeline(mock_extractor, graph_store, vector_store, briefing_gen) -> Pipeline:
    """Fully wired pipeline with all in-memory backends."""
    return Pipeline(
        extractor=mock_extractor,
        graph_store=graph_store,
        vector_store=vector_store,
        briefing_gen=briefing_gen,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Transcript fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _load(filename: str) -> MeetingTranscript:
    p = FIXTURES_DIR / filename
    return MeetingTranscript(
        id=p.stem,
        source_file=str(p),
        text=p.read_text(encoding="utf-8"),
        meeting_title=p.stem.replace("_", " ").title(),
    )


@pytest.fixture
def transcript_01() -> MeetingTranscript:
    return _load("meeting_01.txt")


@pytest.fixture
def transcript_02() -> MeetingTranscript:
    return _load("meeting_02.txt")


@pytest.fixture
def transcript_03() -> MeetingTranscript:
    return _load("meeting_03.txt")


@pytest.fixture
def transcript_04() -> MeetingTranscript:
    return _load("meeting_04.txt")


# ─────────────────────────────────────────────────────────────────────────────
# Integration skip marker
# ─────────────────────────────────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: requires running Docker services (Neo4j, Qdrant)",
    )


def pytest_collection_modifyitems(config, items):
    run_integration = os.getenv("THREADLINE_INTEGRATION", "0") == "1"
    skip_integration = pytest.mark.skip(reason="Set THREADLINE_INTEGRATION=1 to run")
    for item in items:
        if "integration" in item.keywords and not run_integration:
            item.add_marker(skip_integration)
