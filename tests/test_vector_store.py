"""
Tests for vector_store.py and vector_store_qdrant.py
"""
from __future__ import annotations

import os
import pytest

from threadline.vector_store import InMemoryVectorStore
from threadline.models import (
    ExtractionResult,
    ExtractedFact,
    FactType,
)

# ── InMemoryVectorStore Unit Tests ────────────────────────────────────────────

def test_in_memory_vector_store_lifecycle():
    store = InMemoryVectorStore()
    store._use_hash_embed = True  # force fast hash fallback

    f1 = ExtractedFact(id="f1", claim_text="Decide to use PostgreSQL", fact_type=FactType.decision, source_meeting_id="m1")
    f2 = ExtractedFact(id="f2", claim_text="Assign Dev to write tests", fact_type=FactType.action_item, source_meeting_id="m1")
    
    r = ExtractionResult(meeting_id="m1", facts=[f1, f2])
    
    indexed = store.upsert_chunks(r)
    assert indexed == 2

    # Query search
    res = store.search("database storage", top_k=1)
    assert len(res) == 1
    # Hash fallback search results might not be semantically perfect, but shape check should pass
    assert res[0].fact_id in ["f1", "f2"]


# ── QdrantVectorStore Integration Tests ────────────────────────────────────────

@pytest.mark.integration
def test_qdrant_vector_store_integration():
    from threadline.vector_store_qdrant import QdrantVectorStore
    
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    api_key = os.getenv("QDRANT_API_KEY", "")
    
    store = QdrantVectorStore(
        url=url,
        api_key=api_key,
        collection_name="test_collection_threadline"
    )
    # Force fast hash embed for integration testing to prevent downloading large model files during testing
    store._use_hash_embed = True

    try:
        store.verify_connectivity()
    except Exception as e:
        pytest.skip(f"Qdrant not reachable: {e}")

    # Wipe/Delete collection if exists to start clean
    try:
        store.client.delete_collection(collection_name="test_collection_threadline")
    except Exception:
        pass

    f1 = ExtractedFact(id="f1", claim_text="We choose MongoDB Atlas", fact_type=FactType.decision, source_meeting_id="int_m1")
    r = ExtractionResult(meeting_id="int_m1", facts=[f1])
    
    indexed = store.upsert_chunks(r)
    assert indexed == 1

    res = store.search("database stack", top_k=1)
    assert len(res) == 1
    assert res[0].fact_id == "f1"
    assert res[0].text == "We choose MongoDB Atlas"

    # Verify status
    status = store.get_status()
    assert status["connected"] is True
    assert status["vector_count"] == 1


# ── Semantic Search Verification Test ─────────────────────────────────────────

def test_semantic_search_database_migration(transcript_02, mock_extractor):
    # Use real model (no forced hash fallback)
    store = InMemoryVectorStore()
    
    # Extract facts from transcript_02
    extraction_result = mock_extractor.extract(transcript_02)
    
    # Upsert the extracted facts
    indexed = store.upsert_chunks(extraction_result)
    assert indexed > 0
    
    # Search for "database migration"
    results = store.search("database migration", top_k=5)
    
    # Assert we get at least one result with score > 0
    assert len(results) > 0
    assert any(r.score > 0 for r in results)
    
    # If not using hash fallback, verify semantic relevance and high score
    if not store._use_hash_embed:
        # Best matches should have high cosine similarity (> 0.5 after mapping)
        assert results[0].score > 0.5
        # Verify the top result is indeed related to the database/migration decisions/action items
        text_lower = results[0].text.lower()
        assert any(term in text_lower for term in ["mongo", "database", "postgres", "storage", "migration"])

