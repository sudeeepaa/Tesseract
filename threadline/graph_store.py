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
    MeetingSummary,
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
    def get_all_meetings(self) -> list[MeetingSummary]: ...
    def set_meeting_summary(self, meeting_id: str, summary: str) -> None: ...
    def get_graph_snapshot(self) -> GraphSnapshot: ...
    def get_status(self) -> dict[str, Any]: ...
    def purge_person(self, person_name: str) -> dict[str, Any]: ...
    def delete_meeting(self, meeting_id: str) -> dict[str, Any]: ...
    def get_conflict(self, conflict_id: str) -> ConflictRecord | None: ...
    def resolve_conflict(
        self,
        conflict_id:           str,
        choice:                str,
        note:                  str | None = None,
        resolved_by:           str | None = None,
        keep_decision_id:      str | None = None,
        supersede_decision_id: str | None = None,
    ) -> dict[str, Any]:
        """Apply a human decision to a flagged conflict. See ConflictResolutionRequest."""
        ...


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
        self._meeting_ingested_at: dict[str, datetime]     = {}
        self._meeting_summaries: dict[str, str]            = {}
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
        self._meeting_ingested_at.setdefault(meeting_id, _now())

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
            # Mutate status in place, recording WHY it changed (explainability).
            self._decisions[pu.decision_id] = existing.model_copy(
                update={"status": pu.new_status, "status_reason": pu.reason}
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

    def set_meeting_summary(self, meeting_id: str, summary: str) -> None:
        self._meeting_summaries[meeting_id] = summary

    def get_all_meetings(self) -> list[MeetingSummary]:
        dec_by_meeting: dict[str, int] = defaultdict(int)
        for d in self._decisions.values():
            dec_by_meeting[d.source_meeting_id] += 1
        ai_by_meeting: dict[str, int] = defaultdict(int)
        for ai in self._action_items.values():
            ai_by_meeting[ai.source_meeting_id] += 1
        topic_by_meeting: dict[str, int] = defaultdict(int)
        for t in self._topics.values():
            for mid in getattr(t, "source_meeting_ids", []):
                topic_by_meeting[mid] += 1

        summaries = [
            MeetingSummary(
                id=m.id,
                title=m.meeting_title or m.id,
                recorded_at=m.recorded_at,
                ingested_at=self._meeting_ingested_at.get(m.id),
                decision_count=dec_by_meeting.get(m.id, 0),
                action_item_count=ai_by_meeting.get(m.id, 0),
                topic_count=topic_by_meeting.get(m.id, 0),
                preview=(m.text or "").strip().replace("\n", " ")[:160] or None,
                summary=self._meeting_summaries.get(m.id),
            )
            for m in self._meetings.values()
        ]
        # Chronological: recorded time if known, else ingestion time, else id order.
        summaries.sort(key=lambda s: (s.recorded_at or s.ingested_at or _now(), s.id))
        return summaries

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

    def get_conflict(self, conflict_id: str) -> ConflictRecord | None:
        return self._conflicts.get(conflict_id)

    def resolve_conflict(
        self,
        conflict_id:           str,
        choice:                str,
        note:                  str | None = None,
        resolved_by:           str | None = None,
        keep_decision_id:      str | None = None,
        supersede_decision_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Apply a human's decision to a flagged conflict.

        "review" leaves the conflict OPEN (still needs attention) but records
        the note and flags the challenged decision as under_review.  Every other
        choice marks the conflict resolved.
        """
        conflict = self._conflicts.get(conflict_id)
        if conflict is None:
            raise KeyError(f"Conflict {conflict_id!r} not found")

        updated_decisions = 0
        resolved = choice not in ("review", "defer", "deferred")
        # Explainability trace for a human-resolved decision: why the status
        # changed, in the reviewer's own words where they gave one.
        reason_text = f"{conflict.description} — {note}" if note else conflict.description

        # Supersede the losing decision (switch case)
        if supersede_decision_id and supersede_decision_id in self._decisions:
            self._decisions[supersede_decision_id] = self._decisions[
                supersede_decision_id
            ].model_copy(update={"status": DecisionStatus.superseded, "status_reason": reason_text})
            updated_decisions += 1

        # Confirm the winning / kept decision
        if keep_decision_id and keep_decision_id in self._decisions:
            dec = self._decisions[keep_decision_id]
            if dec.status != DecisionStatus.confirmed:
                self._decisions[keep_decision_id] = dec.model_copy(
                    update={"status": DecisionStatus.confirmed, "status_reason": reason_text}
                )
                updated_decisions += 1

        # "review" → flag the challenged decision, keep the conflict open
        if not resolved:
            target = keep_decision_id or (
                conflict.fact_a_id if conflict.fact_a_id in self._decisions else None
            )
            if target and target in self._decisions:
                self._decisions[target] = self._decisions[target].model_copy(
                    update={"status": DecisionStatus.under_review, "status_reason": reason_text}
                )
                updated_decisions += 1

        self._conflicts[conflict_id] = conflict.model_copy(update={
            "resolved":          resolved,
            "resolution_choice": choice,
            "resolution_note":   note,
            "resolved_by":       resolved_by,
            "resolved_at":       _now(),
        })

        return {
            "conflict_id":       conflict_id,
            "resolved":          resolved,
            "choice":            choice,
            "updated_decisions": updated_decisions,
            "summary": (
                "Conflict resolved" if resolved else "Flagged for review (still open)"
            ),
        }

    def purge_person(self, person_name: str) -> dict[str, Any]:
        """Cascade-delete person entity and clear their ownership from decisions and action items."""
        removed_entities = 0
        updated_decisions = 0
        updated_action_items = 0

        # 1. Remove entity matching person_name
        target_ids = []
        for ent_id, ent in list(self._entities.items()):
            if ent.name.lower() == person_name.lower():
                target_ids.append(ent_id)
                del self._entities[ent_id]
                removed_entities += 1

        # Remove edges connected to those entities
        for ent_id in target_ids:
            self._edges = [
                edge for edge in self._edges
                if edge[0] != ent_id and edge[1] != ent_id
            ]

        # 2. Update decisions owner
        for dec_id, dec in self._decisions.items():
            if dec.owner and dec.owner.lower() == person_name.lower():
                self._decisions[dec_id] = dec.model_copy(update={"owner": None})
                updated_decisions += 1

        # 3. Update action items assignee
        for ai_id, ai in self._action_items.items():
            if ai.assignee and ai.assignee.lower() == person_name.lower():
                self._action_items[ai_id] = ai.model_copy(update={"assignee": None})
                updated_action_items += 1

        return {
            "removed_entities": removed_entities,
            "updated_decisions": updated_decisions,
            "updated_action_items": updated_action_items,
        }

    def delete_meeting(self, meeting_id: str) -> dict[str, Any]:
        """Cascade-delete the meeting and all decisions/actions/conflicts/orphaned entities."""
        if meeting_id not in self._meetings:
            return {"status": "not_found", "message": f"Meeting '{meeting_id}' not found"}

        # Track what is deleted
        deleted_decisions = 0
        deleted_action_items = 0
        deleted_conflicts = 0
        deleted_entities = 0
        deleted_topics = 0

        # 1. Delete decisions belonging to this meeting
        for d_id, d in list(self._decisions.items()):
            if d.source_meeting_id == meeting_id:
                del self._decisions[d_id]
                deleted_decisions += 1

        # 2. Delete action items belonging to this meeting
        for a_id, a in list(self._action_items.items()):
            if a.source_meeting_id == meeting_id:
                del self._action_items[a_id]
                deleted_action_items += 1

        # 3. Delete conflicts belonging to this meeting
        for c_id, c in list(self._conflicts.items()):
            if c.meeting_a_id == meeting_id or c.meeting_b_id == meeting_id or c.resolution_meeting_id == meeting_id:
                del self._conflicts[c_id]
                deleted_conflicts += 1

        # 4. Remove the meeting itself
        del self._meetings[meeting_id]
        if meeting_id in self._meeting_summaries:
            del self._meeting_summaries[meeting_id]
        if meeting_id in self._meeting_ingested_at:
            del self._meeting_ingested_at[meeting_id]

        # 5. Clean up edges matching meeting_id or deleted entities/topics
        self._edges = [
            edge for edge in self._edges
            if edge[0] != meeting_id and edge[1] != meeting_id
        ]

        # 6. Orphan cleanup: delete entities and topics with no other meeting relationships
        remaining_meeting_ids = set(self._meetings.keys())
        
        # Check which entities are still connected to any other meeting
        active_entities = set()
        for edge in self._edges:
            # edge format is (source, target, type)
            if edge[1] in remaining_meeting_ids:
                active_entities.add(edge[0])
            elif edge[0] in remaining_meeting_ids:
                active_entities.add(edge[1])

        for e_id in list(self._entities.keys()):
            if e_id not in active_entities:
                del self._entities[e_id]
                deleted_entities += 1

        # Check topics
        active_topics = set()
        for edge in self._edges:
            if edge[1] in remaining_meeting_ids:
                active_topics.add(edge[0])
            elif edge[0] in remaining_meeting_ids:
                active_topics.add(edge[1])

        for t_id in list(self._topics.keys()):
            if t_id not in active_topics:
                del self._topics[t_id]
                deleted_topics += 1

        # Final edge sweep to clean up orphaned node edges
        all_active_nodes = (
            set(self._meetings.keys()) |
            set(self._decisions.keys()) |
            set(self._action_items.keys()) |
            set(self._entities.keys()) |
            set(self._topics.keys()) |
            set(self._conflicts.keys())
        )
        self._edges = [
            edge for edge in self._edges
            if edge[0] in all_active_nodes and edge[1] in all_active_nodes
        ]

        return {
            "status": "success",
            "meeting_id": meeting_id,
            "deleted_decisions": deleted_decisions,
            "deleted_action_items": deleted_action_items,
            "deleted_conflicts": deleted_conflicts,
            "deleted_entities": deleted_entities,
            "deleted_topics": deleted_topics,
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
