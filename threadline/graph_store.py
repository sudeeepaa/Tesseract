"""
Threadline graph store layer.

GraphStore (Protocol)
    InMemoryGraphStore  — dict-based, always available, used as fallback.
    Neo4jGraphStore     — added Day 2.

create_graph_store(settings) — factory with auto-fallback on connection failure.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Protocol, runtime_checkable

from threadline.models import (
    ActionItem,
    ActionItemStatus,
    ConflictRecord,
    Decision,
    DecisionStatus,
    EdgeType,
    Entity,
    ExtractionResult,
    GraphEdge,
    GraphNode,
    GraphSnapshot,
    MeetingTranscript,
    NodeType,
    SupersessionRecord,
    Topic,
    _make_id,
    _now,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Protocol
# ─────────────────────────────────────────────────────────────────────────────

@runtime_checkable
class GraphStore(Protocol):
    def upsert_result(
        self, transcript: MeetingTranscript, result: ExtractionResult
    ) -> dict[str, Any]:
        """Persist an ExtractionResult; return a summary dict for SSE."""
        ...

    def get_all_decisions(self) -> list[Decision]: ...
    def get_all_action_items(self) -> list[ActionItem]: ...
    def get_all_conflicts(self) -> list[ConflictRecord]: ...
    def get_all_topics(self) -> list[str]: ...
    def get_meeting_count(self) -> int: ...
    def get_graph_snapshot(self) -> GraphSnapshot: ...
    def get_status(self) -> dict[str, Any]: ...


# ─────────────────────────────────────────────────────────────────────────────
# InMemoryGraphStore
# ─────────────────────────────────────────────────────────────────────────────

class InMemoryGraphStore:
    """
    Dict-backed graph store.  Used as:
      • the primary store in unit tests (no Docker required)
      • the automatic fallback when Neo4j is unreachable at startup

    State is preserved for the lifetime of the instance — suitable for a
    single process run or a test session where meetings are processed in order.
    """

    def __init__(self) -> None:
        self._meetings:      dict[str, MeetingTranscript]  = {}
        self._decisions:     dict[str, Decision]           = {}
        self._action_items:  dict[str, ActionItem]         = {}
        self._entities:      dict[str, Entity]             = {}
        self._topics:        dict[str, Topic]              = {}
        self._conflicts:     dict[str, ConflictRecord]     = {}
        self._supersessions: dict[str, SupersessionRecord] = {}
        # adjacency for graph snapshot
        self._edges: list[tuple[str, str, EdgeType, bool]] = []

    # ── Write ─────────────────────────────────────────────────────────────────

    def upsert_result(
        self, transcript: MeetingTranscript, result: ExtractionResult
    ) -> dict[str, Any]:
        meeting_id = transcript.id
        self._meetings[meeting_id] = transcript

        new_nodes   = 0
        new_edges   = 0
        supersessions_applied = 0

        # ── New decisions ────────────────────────────────────────────────────
        for d in result.decisions:
            if d.id not in self._decisions:
                new_nodes += 1
            self._decisions[d.id] = d
            # Edge: decision ──MENTIONED_IN──► meeting
            self._add_edge(d.id, meeting_id, EdgeType.mentioned_in, False)
            new_edges += 1

        # ── Prior decision updates (status mutations) ─────────────────────────
        for pu in result.prior_decision_updates:
            existing = self._decisions.get(pu.decision_id)
            if not existing:
                logger.warning("PriorDecisionUpdate references unknown decision %r", pu.decision_id)
                continue
            # Mutate status in place
            self._decisions[pu.decision_id] = existing.model_copy(
                update={"status": pu.new_status}
            )

        # ── Supersession edges ────────────────────────────────────────────────
        for s in result.supersessions:
            self._supersessions[s.id] = s
            # Edge: new ──SUPERSEDES──► old  (superseded=True → dashed in UI)
            self._add_edge(s.new_decision_id, s.old_decision_id, EdgeType.supersedes, True)
            new_edges += 1
            supersessions_applied += 1

        # ── Action items ──────────────────────────────────────────────────────
        for ai in result.action_items:
            if ai.id not in self._action_items:
                new_nodes += 1
            self._action_items[ai.id] = ai
            self._add_edge(ai.id, meeting_id, EdgeType.mentioned_in, False)
            new_edges += 1

        # ── Entities ──────────────────────────────────────────────────────────
        for e in result.entities:
            if e.id in self._entities:
                # Merge meeting IDs into existing entity
                existing_e = self._entities[e.id]
                merged_ids = list(set(existing_e.source_meeting_ids + [meeting_id]))
                self._entities[e.id] = existing_e.model_copy(
                    update={"source_meeting_ids": merged_ids}
                )
            else:
                self._entities[e.id] = e
                new_nodes += 1

        # ── Topics ────────────────────────────────────────────────────────────
        for t in result.topics:
            if t.id in self._topics:
                existing_t = self._topics[t.id]
                merged = list(set(existing_t.source_meeting_ids + [meeting_id]))
                self._topics[t.id] = existing_t.model_copy(
                    update={"source_meeting_ids": merged}
                )
            else:
                self._topics[t.id] = t
                new_nodes += 1

        # ── Conflicts ─────────────────────────────────────────────────────────
        for c in result.new_conflicts:
            if c.resolved and c.id in self._conflicts:
                # Update existing conflict to resolved
                self._conflicts[c.id] = c
                # Add RESOLVES edge
                self._add_edge(meeting_id, c.id, EdgeType.resolves, False)
            elif c.id not in self._conflicts:
                self._conflicts[c.id] = c
                # CONTRADICTS edge
                self._add_edge(c.fact_b_id, c.fact_a_id, EdgeType.contradicts, False)
                new_edges += 1

        summary = {
            "new_nodes": new_nodes,
            "new_edges": new_edges,
            "supersessions_applied": supersessions_applied,
            "total_decisions": len(self._decisions),
            "total_conflicts": len(self._conflicts),
        }
        summary["summary"] = (
            f"{new_nodes} new nodes, {new_edges} new edges"
            + (f", {supersessions_applied} supersession(s)" if supersessions_applied else "")
        )
        return summary

    def _add_edge(
        self, src: str, tgt: str, etype: EdgeType, superseded: bool
    ) -> None:
        # Deduplicate edges
        if (src, tgt, etype, superseded) not in self._edges:
            self._edges.append((src, tgt, etype, superseded))

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_all_decisions(self) -> list[Decision]:
        return list(self._decisions.values())

    def get_all_action_items(self) -> list[ActionItem]:
        return list(self._action_items.values())

    def get_all_conflicts(self) -> list[ConflictRecord]:
        return list(self._conflicts.values())

    def get_all_topics(self) -> list[str]:
        return sorted({t.name for t in self._topics.values()})

    def get_meeting_count(self) -> int:
        return len(self._meetings)

    def get_graph_snapshot(self) -> GraphSnapshot:
        nodes: list[GraphNode] = []

        for m in self._meetings.values():
            nodes.append(GraphNode(
                id=m.id, label=m.meeting_title or m.id,
                type=NodeType.meeting,
                properties={"source_file": m.source_file},
            ))
        for d in self._decisions.values():
            nodes.append(GraphNode(
                id=d.id, label=d.text[:60],
                type=NodeType.decision,
                properties={
                    "status":    d.status.value,
                    "owner":     d.owner or "",
                    "meeting_id": d.source_meeting_id,
                },
            ))
        for ai in self._action_items.values():
            nodes.append(GraphNode(
                id=ai.id, label=ai.text[:60],
                type=NodeType.action_item,
                properties={
                    "assignee": ai.assignee or "",
                    "status":   ai.status.value,
                    "due_date": ai.due_date or "",
                },
            ))
        for e in self._entities.values():
            nodes.append(GraphNode(
                id=e.id, label=e.name,
                type=NodeType.entity,
                properties={"entity_type": e.entity_type.value},
            ))
        for t in self._topics.values():
            nodes.append(GraphNode(
                id=t.id, label=t.name,
                type=NodeType.topic, properties={},
            ))

        edges = [
            GraphEdge(source=src, target=tgt, type=etype, superseded=sup)
            for src, tgt, etype, sup in self._edges
        ]
        return GraphSnapshot(nodes=nodes, edges=edges)

    def get_status(self) -> dict[str, Any]:
        return {
            "connected":    True,
            "backend":      "memory",
            "node_count":   (
                len(self._meetings) + len(self._decisions) +
                len(self._action_items) + len(self._entities) + len(self._topics)
            ),
            "edge_count":   len(self._edges),
            "decision_count": len(self._decisions),
            "conflict_count": len(self._conflicts),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

def create_graph_store(settings) -> GraphStore:
    """
    Returns a Neo4jGraphStore if Neo4j is reachable; otherwise
    falls back to InMemoryGraphStore with a logged warning.
    (Neo4jGraphStore implementation added Day 2.)
    """
    if settings.graph_backend.value == "memory":
        logger.info("Graph backend: InMemory (configured explicitly)")
        return InMemoryGraphStore()

    # Attempt Neo4j connection
    try:
        from threadline.graph_store_neo4j import Neo4jGraphStore
        store = Neo4jGraphStore(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )
        store.verify_connectivity()
        logger.info("Graph backend: Neo4j @ %s", settings.neo4j_uri)
        return store
    except ImportError:
        logger.warning("Neo4jGraphStore not yet implemented — using InMemory fallback")
    except Exception as exc:
        logger.warning(
            "Neo4j unreachable (%s) — degrading to InMemoryGraphStore. "
            "Start Neo4j with: docker-compose up -d neo4j",
            exc,
        )

    return InMemoryGraphStore()
