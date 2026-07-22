"""
Qdrant implementation of the VectorStore protocol.
"""
from __future__ import annotations

import logging
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from threadline.models import (
    ExtractionResult,
    ExtractedFact,
    FactType,
    SearchResult,
)

logger = logging.getLogger(__name__)

class QdrantVectorStore:
    def __init__(
        self,
        url: str,
        api_key: str = "",
        collection_name: str = "threadline_facts",
        embedding_model: str = "all-MiniLM-L6-v2",
        embedding_dim: int = 384,
        embedding_backend: str = "sentence_transformers",
        embedding_api_key: str = "",
    ) -> None:
        from threadline.embeddings import Embedder
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.embedding_dim = embedding_dim
        self.client = QdrantClient(url=url, api_key=api_key)
        self._embedder = Embedder(
            backend=embedding_backend,
            model=embedding_model,
            dim=embedding_dim,
            api_key=embedding_api_key,
        )

        # Lazy check if collection exists; if not, create it
        try:
            self._ensure_collection()
        except Exception as e:
            logger.warning("Could not automatically initialize collection at startup: %s", e)

    def verify_connectivity(self) -> None:
        # Check connection using health endpoint or client call
        self.client.get_collections()

    def _ensure_collection(self) -> None:
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(
                    size=self.embedding_dim,
                    distance=qmodels.Distance.COSINE
                )
            )
            logger.info("Created Qdrant collection: %s", self.collection_name)

    # ── Embedding generation (pluggable: gemini | sentence-transformers | hash) ─

    def _embed_single(self, text: str) -> list[float]:
        return self._embedder.embed_one(text, task="query")

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._embedder.embed(texts, task="document")

    # ── Write ─────────────────────────────────────────────────────────────────

    def upsert_chunks(self, result: ExtractionResult) -> int:
        if not result.facts:
            return 0

        self._ensure_collection()
        texts = [f.claim_text for f in result.facts]
        embs = self._embed_batch(texts)

        points = []
        for i, (fact, emb) in enumerate(zip(result.facts, embs)):
            # Qdrant requires uuid or int as id
            # We construct a deterministic UUID from fact.id if it's not a valid UUID format,
            # or generate a random UUID, or just use fact.id if it's a short hash.
            # Qdrant-client can accept string uuid format.
            import uuid
            # Ensure it is a valid UUID or generate deterministic uuid from fact.id
            try:
                point_id = str(uuid.UUID(fact.id))
            except ValueError:
                # generate deterministic uuid from fact.id namespace
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, fact.id))

            payload = {
                "fact_id": fact.id,
                "text": fact.claim_text,
                "fact_type": fact.fact_type.value,
                "source_meeting_id": fact.source_meeting_id,
                "speaker": fact.speaker or "",
                "ref_id": fact.ref_id or "",
            }
            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=emb,
                    payload=payload
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        logger.debug("Qdrant: indexed %d facts for meeting %s", len(result.facts), result.meeting_id)
        return len(result.facts)

    # ── Read ──────────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        self._ensure_collection()
        q_emb = self._embed_single(query)

        # qdrant-client >= 1.7: client.search() was removed; use query_points() instead.
        # The old client.search() silently caused AttributeError in newer versions,
        # returning nothing. query_points() is the stable replacement.
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=q_emb,
            limit=top_k,
            with_payload=True,
        )
        results_raw = response.points

        # Debug: log top-3 raw scores so misconfigurations are diagnosable
        if results_raw:
            top3 = [(r.score, (r.payload or {}).get("text", "")[:60]) for r in results_raw[:3]]
            logger.info(
                "Qdrant search '%s' — top-3 raw scores: %s",
                query[:60],
                [(round(s, 4), t) for s, t in top3],
            )
        else:
            logger.warning("Qdrant search '%s' returned NO results (collection has %d points)",
                           query[:60], self.client.count(self.collection_name).count)

        search_results = []
        for res in results_raw:
            payload = res.payload or {}
            # Qdrant COSINE distance returns scores in [-1, 1]; clip to [0, 1]
            score = max(0.0, min(1.0, res.score))
            search_results.append(
                SearchResult(
                    fact_id=payload.get("fact_id", str(res.id)),
                    text=payload.get("text", ""),
                    score=score,
                    meeting_id=payload.get("source_meeting_id", ""),
                    speaker=payload.get("speaker"),
                    fact_type=FactType(payload.get("fact_type", "general")),
                )
            )

        # Sort descending by score
        search_results.sort(key=lambda x: x.score, reverse=True)
        return search_results

    def get_status(self) -> dict[str, Any]:
        try:
            self.verify_connectivity()
            info = self.client.get_collection(collection_name=self.collection_name)
            return {
                "connected": True,
                "backend": "qdrant",
                "vector_count": info.points_count,
                "model": self.embedding_model,
                "using_hash_fallback": self._embedder.using_hash_fallback,
            }
        except Exception as e:
            return {
                "connected": False,
                "backend": "qdrant",
                "error": str(e),
            }

    def purge_person(self, person_name: str) -> dict[str, Any]:
        """Delete points from Qdrant where payload speaker matches person_name."""
        try:
            self.verify_connectivity()
            from qdrant_client.http import models as rest_models
            
            # Since Qdrant match is case-sensitive, match speaker by doing a case-insensitive check if possible,
            # or exact match. Qdrant MatchValue works with case-sensitive strings.
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=rest_models.Filter(
                    must=[
                        rest_models.FieldCondition(
                            key="speaker",
                            match=rest_models.MatchValue(value=person_name)
                        )
                    ]
                )
            )
            return {
                "removed_vectors": "unknown_qdrant_cascade",
                "status": "success"
            }
        except Exception as e:
            logger.error("Qdrant purge failed: %s", e)
            return {
                "removed_vectors": 0,
                "error": str(e)
            }

    def delete_meeting(self, meeting_id: str) -> dict[str, Any]:
        """Delete all points from Qdrant where source_meeting_id matches meeting_id."""
        try:
            self.verify_connectivity()
            from qdrant_client.http import models as rest_models
            
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=rest_models.Filter(
                    must=[
                        rest_models.FieldCondition(
                            key="source_meeting_id",
                            match=rest_models.MatchValue(value=meeting_id)
                        )
                    ]
                )
            )
            return {
                "status": "success",
                "meeting_id": meeting_id,
                "removed_vectors": "unknown_qdrant_cascade",
            }
        except Exception as e:
            logger.error("Qdrant delete_meeting failed: %s", e)
            return {
                "status": "error",
                "meeting_id": meeting_id,
                "removed_vectors": 0,
                "error": str(e)
            }

