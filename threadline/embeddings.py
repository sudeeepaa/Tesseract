"""
Pluggable text embedding for the vector stores.

Backends:
    - ``gemini``               → Google Gemini embeddings (hosted API, no local model,
                                 tiny memory footprint; used in production on Render).
    - ``sentence_transformers``→ local all-MiniLM-L6-v2 via torch (rich local dev).
    - ``hash``                 → deterministic pseudo-embeddings (tests / no deps).

All backends resolve lazily on first use and degrade gracefully: a missing key,
missing dependency, or a failed call falls back to hash embeddings so the pipeline
never crashes. Vectors are L2-normalized so InMemory cosine (a plain dot product)
and Qdrant COSINE both behave.
"""
from __future__ import annotations

import hashlib
import logging
import math
import os
import random

logger = logging.getLogger(__name__)


def _normalize(vec: list[float]) -> list[float]:
    mag = math.sqrt(sum(x * x for x in vec))
    return [x / mag for x in vec] if mag > 1e-9 else vec


def hash_embed(text: str, dim: int) -> list[float]:
    """Deterministic pseudo-embedding from an MD5 seed. Semantically meaningless."""
    seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
    rng = random.Random(seed)
    return _normalize([rng.gauss(0, 1) for _ in range(dim)])


class Embedder:
    """
    Lazily-resolved text embedder shared by InMemory and Qdrant stores.

    ``task`` maps to Gemini's ``task_type`` (retrieval_document for indexing,
    retrieval_query for search) and is ignored by the other backends.
    """

    def __init__(
        self,
        backend: str = "sentence_transformers",
        model: str = "all-MiniLM-L6-v2",
        dim: int = 384,
        api_key: str = "",
    ) -> None:
        self.backend = (backend or "sentence_transformers").lower()
        self.model = model
        self.dim = dim
        self.api_key = api_key
        self.resolved: str | None = None   # "gemini" | "st" | "hash"
        self._genai = None
        self._st_model = None

    # ── Resolution (lazy) ──────────────────────────────────────────────────────

    def _resolve(self) -> None:
        if self.resolved is not None:
            return

        if self.backend == "gemini":
            if not self.api_key:
                logger.warning("EMBEDDING_BACKEND=gemini but no API key — hash fallback")
                self.resolved = "hash"
                return
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._genai = genai
                self.resolved = "gemini"
                logger.info("Embedder: Gemini %s (%dd)", self.model, self.dim)
                return
            except Exception as exc:
                logger.warning("Gemini embeddings unavailable (%s) — hash fallback", exc)
                self.resolved = "hash"
                return

        if self.backend in ("sentence_transformers", "st", "local"):
            # Keep tests hermetic and offline.
            if os.environ.get("THREADLINE_TESTING") == "1":
                self.resolved = "hash"
                logger.info("Test environment detected: forcing hash embeddings.")
                return
            try:
                from sentence_transformers import SentenceTransformer
                self._st_model = SentenceTransformer(self.model)
                self.resolved = "st"
                logger.debug("Embedder: sentence-transformers %s", self.model)
                return
            except Exception as exc:
                logger.warning("sentence-transformers unavailable (%s) — hash fallback", exc)
                self.resolved = "hash"
                return

        self.resolved = "hash"

    @property
    def using_hash_fallback(self) -> bool:
        return self.resolved == "hash"

    # ── Embedding ──────────────────────────────────────────────────────────────

    def embed(self, texts: list[str], task: str = "document") -> list[list[float]]:
        self._resolve()
        if not texts:
            return []
        if self.resolved == "gemini":
            return self._embed_gemini(texts, task)
        if self.resolved == "st":
            embs = self._st_model.encode(texts, normalize_embeddings=True, batch_size=64)
            return [e.tolist() for e in embs]
        return [hash_embed(t, self.dim) for t in texts]

    def embed_one(self, text: str, task: str = "query") -> list[float]:
        return self.embed([text], task=task)[0]

    def _embed_gemini(self, texts: list[str], task: str) -> list[list[float]]:
        task_type = "retrieval_query" if task == "query" else "retrieval_document"
        # gemini-embedding-001 defaults to 3072 dims; request the configured size
        # via Matryoshka truncation. Truncated vectors aren't unit-norm, so we
        # always re-normalize below (InMemory cosine assumes normalized vectors).
        try:
            resp = self._genai.embed_content(
                model=self.model, content=texts, task_type=task_type,
                output_dimensionality=self.dim,
            )
            embs = resp["embedding"] if isinstance(resp, dict) else resp.embedding
            # A single-string content returns a flat vector; a list returns a list
            # of vectors. Normalize to list-of-vectors.
            if embs and isinstance(embs[0], (int, float)):
                embs = [embs]
            return [_normalize(list(e)) for e in embs]
        except Exception as exc:
            logger.warning("Gemini batch embed failed (%s) — retrying per item", exc)

        out: list[list[float]] = []
        for t in texts:
            try:
                r = self._genai.embed_content(
                    model=self.model, content=t, task_type=task_type,
                    output_dimensionality=self.dim,
                )
                v = r["embedding"] if isinstance(r, dict) else r.embedding
                out.append(_normalize(list(v)))
            except Exception as exc:
                logger.warning("Gemini embed failed for one item (%s) — hash", exc)
                out.append(hash_embed(t, self.dim))
        return out
