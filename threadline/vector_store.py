"""
Threadline vector store layer.

VectorStore (Protocol)
    InMemoryVectorStore  — uses sentence-transformers for real semantic search.
                           Falls back to hash-based pseudo-embeddings if
                           sentence-transformers is not installed (test environments).
    QdrantVectorStore    — added Day 2.

create_vector_store(settings) — factory with auto-fallback on connection failure.
"""
from __future__ import annotations

import hashlib
import logging
import math
import random
from typing import Any, Protocol, runtime_checkable

from threadline.models import (
    ExtractionResult,
    ExtractedFact,
    FactType,
    SearchResult,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Protocol
# ─────────────────────────────────────────────────────────────────────────────

@runtime_checkable
class VectorStore(Protocol):
    def upsert_chunks(self, result: ExtractionResult) -> int:
        """Index all facts from an ExtractionResult. Returns chunk count."""
        ...

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Semantic search. Returns ranked results."""
        ...

    def get_status(self) -> dict[str, Any]: ...
    def purge_person(self, person_name: str) -> dict[str, Any]: ...
    def delete_meeting(self, meeting_id: str) -> dict[str, Any]: ...


# ─────────────────────────────────────────────────────────────────────────────
# InMemoryVectorStore
# ─────────────────────────────────────────────────────────────────────────────

def _normalize(vec: list[float]) -> list[float]:
    mag = math.sqrt(sum(x * x for x in vec))
    if mag < 1e-9:
        return vec
    return [x / mag for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _hash_embed(text: str, dim: int = 384) -> list[float]:
    """
    Deterministic pseudo-embedding from MD5 hash.
    Used ONLY when sentence-transformers is not installed (e.g. CI with no GPU).
    Semantics are meaningless but the interface contract is satisfied.
    """
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
    rng  = random.Random(seed)
    vec  = [rng.gauss(0, 1) for _ in range(dim)]
    return _normalize(vec)


class InMemoryVectorStore:
    """
    Sentence-transformers backed in-memory vector store.

    The model is loaded lazily on first use so startup is fast.
    If sentence-transformers is unavailable the store transparently falls back
    to hash-based embeddings — functional for the Protocol contract but not
    semantically meaningful.

    Per the implementation plan, the Docker build pre-downloads the model so
    there is no cold-download penalty during the demo:
        RUN python -c "from sentence_transformers import SentenceTransformer; \\
                       SentenceTransformer('all-MiniLM-L6-v2')"
    """

    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        embedding_dim:   int = 384,
    ) -> None:
        self._embedding_model = embedding_model
        self._embedding_dim   = embedding_dim
        self._model           = None          # lazy-loaded
        self._use_hash_embed  = False         # set True if ST unavailable
        self._facts:      list[ExtractedFact] = []
        self._embeddings: list[list[float]]   = []

    # ── Embedding ─────────────────────────────────────────────────────────────

    def _load_model(self) -> None:
        if self._model is not None or self._use_hash_embed:
            return
        import os
        if os.environ.get("THREADLINE_TESTING") == "1":
            self._use_hash_embed = True
            logger.info("Test environment detected: forcing pseudo-embeddings fallback.")
            return
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._embedding_model)
            logger.debug("sentence-transformers model loaded: %s", self._embedding_model)
        except ImportError:
            logger.warning(
                "sentence-transformers not installed; using hash-based embeddings. "
                "Search results will not be semantically meaningful. "
                "Install with: pip install sentence-transformers"
            )
            self._use_hash_embed = True
        except Exception as exc:
            logger.warning("Failed to load embedding model: %s — using hash fallback", exc)
            self._use_hash_embed = True

    def _embed_single(self, text: str) -> list[float]:
        self._load_model()
        if self._use_hash_embed:
            return _hash_embed(text, self._embedding_dim)
        emb = self._model.encode([text], normalize_embeddings=True)
        return emb[0].tolist()

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        self._load_model()
        if self._use_hash_embed:
            return [_hash_embed(t, self._embedding_dim) for t in texts]
        embs = self._model.encode(texts, normalize_embeddings=True, batch_size=64)
        return [e.tolist() for e in embs]

    # ── Write ─────────────────────────────────────────────────────────────────

    def upsert_chunks(self, result: ExtractionResult) -> int:
        if not result.facts:
            return 0
        texts = [f.claim_text for f in result.facts]
        embs  = self._embed_batch(texts)
        for fact, emb in zip(result.facts, embs):
            self._facts.append(fact)
            self._embeddings.append(emb)
        logger.debug(
            "VectorStore: indexed %d chunks for meeting %s",
            len(result.facts), result.meeting_id,
        )
        return len(result.facts)

    # ── Read ──────────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        if not self._facts:
            return []
        q_emb  = self._embed_single(query)
        scores = [(i, _cosine(q_emb, emb)) for i, emb in enumerate(self._embeddings)]
        scores.sort(key=lambda x: x[1], reverse=True)

        # Debug: log top-3 raw cosine scores before normalization
        top3_raw = [(round(s, 4), self._facts[i].claim_text[:60]) for i, s in scores[:3]]
        logger.info(
            "InMemory search '%s' — top-3 raw scores: %s",
            query[:60], top3_raw,
        )

        results: list[SearchResult] = []
        for i, score in scores[:top_k]:
            fact = self._facts[i]
            results.append(SearchResult(
                fact_id=fact.id,
                text=fact.claim_text,
                score=max(0.0, min(1.0, (score + 1.0) / 2.0)),  # map [-1,1]→[0,1]
                meeting_id=fact.source_meeting_id,
                speaker=fact.speaker,
                fact_type=fact.fact_type,
            ))
        return results

    def get_status(self) -> dict[str, Any]:
        return {
            "connected":    True,
            "backend":      "memory",
            "vector_count": len(self._facts),
            "model":        self._embedding_model,
            "using_hash_fallback": self._use_hash_embed,
        }

    def purge_person(self, person_name: str) -> dict[str, Any]:
        """Remove all indexed facts where the speaker matches person_name."""
        initial_count = len(self._facts)
        new_facts = []
        new_embeddings = []
        
        for fact, emb in zip(self._facts, self._embeddings):
            is_match = False
            if fact.speaker and fact.speaker.lower() == person_name.lower():
                is_match = True
            if not is_match:
                new_facts.append(fact)
                new_embeddings.append(emb)
                
        self._facts = new_facts
        self._embeddings = new_embeddings
        removed = initial_count - len(self._facts)
        return {
            "removed_vectors": removed,
        }

    def delete_meeting(self, meeting_id: str) -> dict[str, Any]:
        """Remove all indexed facts belonging to meeting_id."""
        initial_count = len(self._facts)
        new_facts = []
        new_embeddings = []
        
        for fact, emb in zip(self._facts, self._embeddings):
            if fact.source_meeting_id != meeting_id:
                new_facts.append(fact)
                new_embeddings.append(emb)
                
        self._facts = new_facts
        self._embeddings = new_embeddings
        removed = initial_count - len(self._facts)
        return {
            "status": "success",
            "meeting_id": meeting_id,
            "removed_vectors": removed,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

def create_vector_store(settings) -> VectorStore:
    """
    Returns a QdrantVectorStore if Qdrant is reachable; otherwise
    falls back to InMemoryVectorStore with a logged warning.
    (QdrantVectorStore implementation added Day 2.)
    """
    if settings.vector_backend.value == "memory":
        logger.info("Vector backend: InMemory (configured explicitly)")
        return InMemoryVectorStore(
            embedding_model=settings.embedding_model,
            embedding_dim=settings.embedding_dim,
        )

    try:
        from threadline.vector_store_qdrant import QdrantVectorStore
        store = QdrantVectorStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            collection_name=settings.qdrant_collection,
            embedding_model=settings.embedding_model,
            embedding_dim=settings.embedding_dim,
        )
        store.verify_connectivity()
        logger.info("Vector backend: Qdrant @ %s", settings.qdrant_url)
        return store
    except ImportError:
        logger.warning("QdrantVectorStore not yet implemented — using InMemory fallback")
    except Exception as exc:
        logger.warning(
            "Qdrant unreachable (%s) — degrading to InMemoryVectorStore. "
            "Start Qdrant with: docker-compose up -d qdrant",
            exc,
        )

    return InMemoryVectorStore(
        embedding_model=settings.embedding_model,
        embedding_dim=settings.embedding_dim,
    )
