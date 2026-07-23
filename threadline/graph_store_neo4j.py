"""
Neo4j implementation of the GraphStore protocol.
"""
from __future__ import annotations

import logging
from typing import Any

from neo4j import GraphDatabase

from threadline.models import (
    ActionItem,
    ActionItemStatus,
    ConflictRecord,
    Decision,
    DecisionStatus,
    EdgeType,
    Entity,
    EntityType,
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

class Neo4jGraphStore:
    def __init__(self, uri: str, user: str, password: str) -> None:
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def verify_connectivity(self) -> None:
        self.driver.verify_connectivity()

    def close(self) -> None:
        self.driver.close()

    def upsert_result(
        self, transcript: MeetingTranscript, result: ExtractionResult
    ) -> dict[str, Any]:
        meeting_id = transcript.id

        # We will perform the operations in a single transaction or multiple.
        # Running inside a write transaction ensures consistency.
        with self.driver.session() as session:
            stats = session.execute_write(self._write_tx, transcript, result)
        return stats

    def _write_tx(self, tx: Any, transcript: MeetingTranscript, result: ExtractionResult) -> dict[str, Any]:
        meeting_id = transcript.id
        
        # 1. Merge Meeting node
        tx.run(
            """
            MERGE (m:Meeting {id: $id})
            ON CREATE SET m.source_file = $source_file,
                          m.text = $text,
                          m.meeting_title = $meeting_title,
                          m.recorded_at = $recorded_at,
                          m.ingested_at = $ingested_at
            ON MATCH SET m.source_file = $source_file,
                         m.text = $text,
                         m.meeting_title = $meeting_title
            """,
            id=meeting_id,
            source_file=transcript.source_file,
            text=transcript.text,
            meeting_title=transcript.meeting_title or meeting_id,
            recorded_at=transcript.recorded_at.isoformat() if transcript.recorded_at else None,
            ingested_at=_now().isoformat(),
        )

        new_nodes = 0
        new_edges = 0
        supersessions_applied = 0

        # ── Decisions ────────────────────────────────────────────────────────
        for d in result.decisions:
            # Check if decision already exists
            res = tx.run("MATCH (d:Decision {id: $id}) RETURN d", id=d.id)
            if not res.peek():
                new_nodes += 1
            
            tx.run(
                """
                MERGE (d:Decision {id: $id})
                SET d.text = $text,
                    d.status = $status,
                    d.rationale = $rationale,
                    d.owner = $owner,
                    d.source_meeting_id = $source_meeting_id
                """,
                id=d.id,
                text=d.text,
                status=d.status.value,
                rationale=d.rationale,
                owner=d.owner,
                source_meeting_id=d.source_meeting_id,
            )

            # Edge: Decision ──MENTIONED_IN──► Meeting
            res_edge = tx.run(
                """
                MATCH (d:Decision {id: $d_id}), (m:Meeting {id: $m_id})
                MERGE (d)-[r:MENTIONED_IN]->(m)
                ON CREATE SET r.superseded = false
                RETURN r
                """,
                d_id=d.id,
                m_id=meeting_id,
            )
            if res_edge.consume().counters.relationships_created > 0:
                new_edges += 1

        # ── Prior Decision Updates (status mutations) ─────────────────────────
        for pu in result.prior_decision_updates:
            tx.run(
                """
                MATCH (d:Decision {id: $id})
                SET d.status = $new_status,
                    d.status_reason = $reason
                """,
                id=pu.decision_id,
                new_status=pu.new_status.value,
                reason=pu.reason,
            )

        # ── Supersessions ────────────────────────────────────────────────────
        for s in result.supersessions:
            # Create SUPERSEDES relationship
            # Edge: new ──SUPERSEDES──► old (superseded = true)
            res_edge = tx.run(
                """
                MATCH (new:Decision {id: $new_id}), (old:Decision {id: $old_id})
                MERGE (new)-[r:SUPERSEDES]->(old)
                SET r.superseded = true, r.reason = $reason, r.meeting_id = $meeting_id
                RETURN r
                """,
                new_id=s.new_decision_id,
                old_id=s.old_decision_id,
                reason=s.reason,
                meeting_id=s.meeting_id,
            )
            if res_edge.consume().counters.relationships_created > 0:
                new_edges += 1
                supersessions_applied += 1

        # Also draw SUPERSEDES from a new decision's supersedes_decision_id — the
        # reliable signal the LLM emits (it can't fill a prior-update's
        # new_decision_id with the new decision's random id, so `supersessions`
        # is often empty even though a replacement happened). MERGE dedupes.
        for d in result.decisions:
            if not d.supersedes_decision_id or d.supersedes_decision_id == d.id:
                continue
            res_edge = tx.run(
                """
                MATCH (new:Decision {id: $new_id}), (old:Decision {id: $old_id})
                MERGE (new)-[r:SUPERSEDES]->(old)
                SET r.superseded = true
                SET old.status = 'superseded',
                    old.status_reason = coalesce(old.status_reason, $reason)
                RETURN r
                """,
                new_id=d.id,
                old_id=d.supersedes_decision_id,
                reason=f"Replaced by “{d.text}”.",
            )
            if res_edge.consume().counters.relationships_created > 0:
                new_edges += 1
                supersessions_applied += 1

        # ── Action Items ──────────────────────────────────────────────────────
        for ai in result.action_items:
            res = tx.run("MATCH (a:ActionItem {id: $id}) RETURN a", id=ai.id)
            if not res.peek():
                new_nodes += 1
            
            tx.run(
                """
                MERGE (a:ActionItem {id: $id})
                SET a.text = $text,
                    a.assignee = $assignee,
                    a.due_date = $due_date,
                    a.status = $status,
                    a.source_meeting_id = $source_meeting_id
                """,
                id=ai.id,
                text=ai.text,
                assignee=ai.assignee,
                due_date=ai.due_date,
                status=ai.status.value,
                source_meeting_id=ai.source_meeting_id,
            )

            # Edge: ActionItem ──MENTIONED_IN──► Meeting
            res_edge = tx.run(
                """
                MATCH (a:ActionItem {id: $a_id}), (m:Meeting {id: $m_id})
                MERGE (a)-[r:MENTIONED_IN]->(m)
                ON CREATE SET r.superseded = false
                RETURN r
                """,
                a_id=ai.id,
                m_id=meeting_id,
            )
            if res_edge.consume().counters.relationships_created > 0:
                new_edges += 1

        # ── Entities ──────────────────────────────────────────────────────────
        for e in result.entities:
            # We construct a deterministic ID for entities based on name if they don't have one
            entity_id = e.id or f"ent_{e.name.lower().replace(' ', '_')}"
            res = tx.run("MATCH (en:Entity {id: $id}) RETURN en", id=entity_id)
            if not res.peek():
                new_nodes += 1
            
            tx.run(
                """
                MERGE (en:Entity {id: $id})
                SET en.name = $name,
                    en.entity_type = $entity_type
                """,
                id=entity_id,
                name=e.name,
                entity_type=e.entity_type.value,
            )

            # Link Entity to Meeting
            res_edge = tx.run(
                """
                MATCH (en:Entity {id: $en_id}), (m:Meeting {id: $m_id})
                MERGE (en)-[r:MENTIONED_IN]->(m)
                ON CREATE SET r.superseded = false
                RETURN r
                """,
                en_id=entity_id,
                m_id=meeting_id,
            )
            if res_edge.consume().counters.relationships_created > 0:
                new_edges += 1

        # ── Topics ────────────────────────────────────────────────────────────
        for t in result.topics:
            topic_id = t.id or f"topic_{t.name.lower().replace(' ', '_')}"
            res = tx.run("MATCH (tp:Topic {id: $id}) RETURN tp", id=topic_id)
            if not res.peek():
                new_nodes += 1
            
            tx.run(
                """
                MERGE (tp:Topic {id: $id})
                SET tp.name = $name
                """,
                id=topic_id,
                name=t.name,
            )

            # Link Topic to Meeting
            res_edge = tx.run(
                """
                MATCH (tp:Topic {id: $tp_id}), (m:Meeting {id: $m_id})
                MERGE (tp)-[r:MENTIONED_IN]->(m)
                ON CREATE SET r.superseded = false
                RETURN r
                """,
                tp_id=topic_id,
                m_id=meeting_id,
            )
            if res_edge.consume().counters.relationships_created > 0:
                new_edges += 1

        # ── Conflicts ─────────────────────────────────────────────────────────
        for c in result.new_conflicts:
            # Merge Conflict Node
            res_c = tx.run("MATCH (cf:Conflict {id: $id}) RETURN cf", id=c.id)
            if not res_c.peek():
                new_nodes += 1

            tx.run(
                """
                MERGE (cf:Conflict {id: $id})
                SET cf.description = $description,
                    cf.resolved = $resolved,
                    cf.fact_a_id = $fact_a_id,
                    cf.fact_b_id = $fact_b_id,
                    cf.fact_a_text = $fact_a_text,
                    cf.fact_b_text = $fact_b_text,
                    cf.meeting_a_id = $meeting_a_id,
                    cf.meeting_b_id = $meeting_b_id,
                    cf.resolution_meeting_id = $resolution_meeting_id,
                    cf.confidence = $confidence,
                    cf.reasoning = $reasoning
                """,
                id=c.id,
                description=c.description,
                resolved=c.resolved,
                fact_a_id=c.fact_a_id,
                fact_b_id=c.fact_b_id,
                fact_a_text=c.fact_a_text,
                fact_b_text=c.fact_b_text,
                meeting_a_id=c.meeting_a_id,
                meeting_b_id=c.meeting_b_id,
                resolution_meeting_id=c.resolution_meeting_id,
                confidence=c.confidence,
                reasoning=c.reasoning,
            )

            if c.resolved:
                # Edge: meeting ──RESOLVES──► conflict
                res_edge = tx.run(
                    """
                    MATCH (m:Meeting {id: $m_id}), (cf:Conflict {id: $c_id})
                    MERGE (m)-[r:RESOLVES]->(cf)
                    ON CREATE SET r.superseded = false
                    RETURN r
                    """,
                    m_id=meeting_id,
                    c_id=c.id,
                )
                if res_edge.consume().counters.relationships_created > 0:
                    new_edges += 1
            else:
                # Edge: fact_b ──CONTRADICTS──► fact_a
                # In Neo4j, we can link Decision node or Meeting node as representational
                res_edge = tx.run(
                    """
                    MATCH (fb:Decision {id: $fb_id}), (fa:Decision {id: $fa_id})
                    MERGE (fb)-[r:CONTRADICTS]->(fa)
                    ON CREATE SET r.superseded = false
                    RETURN r
                    """,
                    fb_id=c.fact_b_id if c.fact_b_id.startswith("dec") else meeting_id,
                    fa_id=c.fact_a_id,
                )
                if res_edge.consume().counters.relationships_created > 0:
                    new_edges += 1

        # Fetch current decision count and conflict count in this session
        res_dec = tx.run("MATCH (d:Decision) RETURN count(d) as total_decisions")
        total_decisions = res_dec.single()["total_decisions"]

        res_cf = tx.run("MATCH (cf:Conflict) RETURN count(cf) as total_conflicts")
        total_conflicts = res_cf.single()["total_conflicts"]

        summary = {
            "new_nodes": new_nodes,
            "new_edges": new_edges,
            "supersessions_applied": supersessions_applied,
            "total_decisions": total_decisions,
            "total_conflicts": total_conflicts,
        }
        summary["summary"] = (
            f"{new_nodes} new nodes, {new_edges} new edges"
            + (f", {supersessions_applied} supersession(s)" if supersessions_applied else "")
        )
        return summary

    # ── Read methods ──────────────────────────────────────────────────────────

    def get_all_decisions(self) -> list[Decision]:
        with self.driver.session() as session:
            res = session.run("MATCH (d:Decision) RETURN d")
            decisions = []
            for record in res:
                node = record["d"]
                decisions.append(Decision(
                    id=node["id"],
                    text=node["text"],
                    status=DecisionStatus(node["status"]),
                    rationale=node.get("rationale"),
                    owner=node.get("owner"),
                    source_meeting_id=node["source_meeting_id"],
                    status_reason=node.get("status_reason"),
                    review_note=node.get("review_note"),
                    reviewed_by=node.get("reviewed_by"),
                ))
            return decisions

    def get_all_action_items(self) -> list[ActionItem]:
        with self.driver.session() as session:
            res = session.run("MATCH (a:ActionItem) RETURN a")
            items = []
            for record in res:
                node = record["a"]
                items.append(ActionItem(
                    id=node["id"],
                    text=node["text"],
                    assignee=node.get("assignee"),
                    due_date=node.get("due_date"),
                    status=ActionItemStatus(node["status"]),
                    source_meeting_id=node["source_meeting_id"],
                ))
            return items

    def get_all_conflicts(self) -> list[ConflictRecord]:
        with self.driver.session() as session:
            res = session.run("MATCH (cf:Conflict) RETURN cf")
            conflicts = []
            for record in res:
                node = record["cf"]
                conflicts.append(ConflictRecord(
                    id=node["id"],
                    fact_a_id=node["fact_a_id"],
                    fact_b_id=node["fact_b_id"],
                    fact_a_text=node.get("fact_a_text", ""),
                    fact_b_text=node.get("fact_b_text", ""),
                    description=node["description"],
                    meeting_a_id=node["meeting_a_id"],
                    meeting_b_id=node["meeting_b_id"],
                    resolved=node["resolved"],
                    resolution_meeting_id=node.get("resolution_meeting_id"),
                    confidence=node.get("confidence", 1.0),
                    reasoning=node.get("reasoning"),
                    resolution_choice=node.get("resolution_choice"),
                    resolution_note=node.get("resolution_note"),
                    resolved_by=node.get("resolved_by"),
                ))
            return conflicts

    def get_conflict(self, conflict_id: str) -> ConflictRecord | None:
        for c in self.get_all_conflicts():
            if c.id == conflict_id:
                return c
        return None

    def resolve_conflict(
        self,
        conflict_id:           str,
        choice:                str,
        note:                  str | None = None,
        resolved_by:           str | None = None,
        keep_decision_id:      str | None = None,
        supersede_decision_id: str | None = None,
    ) -> dict[str, Any]:
        with self.driver.session() as session:
            return session.execute_write(
                self._resolve_tx, conflict_id, choice, note,
                resolved_by, keep_decision_id, supersede_decision_id,
            )

    def _resolve_tx(
        self, tx: Any, conflict_id: str, choice: str, note: str | None,
        resolved_by: str | None, keep_decision_id: str | None,
        supersede_decision_id: str | None,
    ) -> dict[str, Any]:
        cf_record = tx.run("MATCH (cf:Conflict {id: $id}) RETURN cf", id=conflict_id).single()
        if not cf_record:
            raise KeyError(f"Conflict {conflict_id!r} not found")

        from datetime import datetime, timezone
        updated_decisions = 0
        resolved = choice not in ("review", "defer", "deferred")
        # Explainability trace for a human-resolved decision: why the status
        # changed, in the reviewer's own words where they gave one.
        description = cf_record["cf"].get("description", "")
        reason_text = f"{description} — {note}" if note else description

        if supersede_decision_id:
            r = tx.run(
                "MATCH (d:Decision {id: $id}) SET d.status = 'superseded', d.status_reason = $reason RETURN d",
                id=supersede_decision_id, reason=reason_text,
            )
            if r.peek():
                updated_decisions += 1

        if keep_decision_id:
            r = tx.run(
                "MATCH (d:Decision {id: $id}) SET d.status = 'confirmed', d.status_reason = $reason RETURN d",
                id=keep_decision_id, reason=reason_text,
            )
            if r.peek():
                updated_decisions += 1

        if not resolved and keep_decision_id:
            tx.run(
                "MATCH (d:Decision {id: $id}) SET d.status = 'under_review', d.status_reason = $reason",
                id=keep_decision_id, reason=reason_text,
            )

        tx.run(
            """
            MATCH (cf:Conflict {id: $id})
            SET cf.resolved = $resolved,
                cf.resolution_choice = $choice,
                cf.resolution_note = $note,
                cf.resolved_by = $resolved_by,
                cf.resolved_at = $resolved_at
            """,
            id=conflict_id,
            resolved=resolved,
            choice=choice,
            note=note,
            resolved_by=resolved_by,
            resolved_at=datetime.now(timezone.utc).isoformat(),
        )

        if resolved and keep_decision_id:
            tx.run(
                """
                MATCH (d:Decision {id: $kid}), (cf:Conflict {id: $cid})
                MERGE (d)-[r:RESOLVES]->(cf)
                ON CREATE SET r.superseded = false
                """,
                kid=keep_decision_id,
                cid=conflict_id,
            )

        return {
            "conflict_id":       conflict_id,
            "resolved":          resolved,
            "choice":            choice,
            "updated_decisions": updated_decisions,
            "summary": (
                "Conflict resolved" if resolved else "Flagged for review (still open)"
            ),
        }

    def review_decision(
        self,
        decision_id: str,
        action:      str,
        note:        str | None = None,
        reviewed_by: str | None = None,
    ) -> dict[str, Any]:
        """Apply a human review to one decision. See DecisionReviewRequest."""
        status_map = {"approve": "confirmed", "reject": "reversed"}
        if action not in ("approve", "reject", "comment"):
            raise ValueError(f"Unknown review action {action!r}")
        with self.driver.session() as session:
            exists = session.run(
                "MATCH (d:Decision {id: $id}) RETURN d", id=decision_id
            ).single()
            if not exists:
                raise KeyError(f"Decision {decision_id!r} not found")

            if action == "comment":
                session.run(
                    "MATCH (d:Decision {id: $id}) SET d.review_note = $note, d.reviewed_by = $by",
                    id=decision_id, note=note, by=reviewed_by,
                )
                new_status = exists["d"].get("status")
            else:
                new_status = status_map[action]
                session.run(
                    """
                    MATCH (d:Decision {id: $id})
                    SET d.status = $status, d.review_note = $note, d.reviewed_by = $by
                    """,
                    id=decision_id, status=new_status, note=note, by=reviewed_by,
                )
        summary = {"approve": "Decision approved", "reject": "Decision rejected"}.get(action, "Comment added")
        return {
            "decision_id": decision_id,
            "action":      action,
            "new_status":  new_status,
            "summary":     summary,
        }

    def get_all_topics(self) -> list[str]:
        with self.driver.session() as session:
            res = session.run("MATCH (t:Topic) RETURN t.name as name")
            return sorted({record["name"] for record in res})

    def get_meeting_count(self) -> int:
        with self.driver.session() as session:
            res = session.run("MATCH (m:Meeting) RETURN count(m) as count")
            return res.single()["count"]

    def get_all_meetings(self) -> list[MeetingSummary]:
        from datetime import datetime

        def _parse(dt: Any):
            if not dt:
                return None
            try:
                return datetime.fromisoformat(str(dt))
            except Exception:
                return None

        with self.driver.session() as session:
            rows = session.run(
                """
                MATCH (m:Meeting)
                OPTIONAL MATCH (d:Decision)-[:MENTIONED_IN]->(m)
                OPTIONAL MATCH (a:ActionItem)-[:MENTIONED_IN]->(m)
                OPTIONAL MATCH (t:Topic)-[:MENTIONED_IN]->(m)
                RETURN m.id AS id, m.meeting_title AS title,
                       m.recorded_at AS recorded_at, m.ingested_at AS ingested_at,
                       m.text AS text, m.summary AS summary,
                       count(DISTINCT d) AS decisions,
                       count(DISTINCT a) AS actions,
                       count(DISTINCT t) AS topics
                ORDER BY coalesce(m.recorded_at, m.ingested_at, m.id), m.id
                """
            ).data()

        return [
            MeetingSummary(
                id=r["id"],
                title=r.get("title") or r["id"],
                recorded_at=_parse(r.get("recorded_at")),
                ingested_at=_parse(r.get("ingested_at")),
                decision_count=r.get("decisions", 0),
                action_item_count=r.get("actions", 0),
                topic_count=r.get("topics", 0),
                preview=((r.get("text") or "").strip().replace("\n", " ")[:160] or None),
                summary=r.get("summary"),
            )
            for r in rows
        ]

    def set_meeting_summary(self, meeting_id: str, summary: str) -> None:
        with self.driver.session() as session:
            session.run(
                "MATCH (m:Meeting {id: $id}) SET m.summary = $summary",
                id=meeting_id, summary=summary,
            )

    def get_graph_snapshot(self) -> GraphSnapshot:
        with self.driver.session() as session:
            # Query all nodes
            res_nodes = session.run(
                """
                MATCH (n)
                RETURN id(n) as internal_id, labels(n) as labels, properties(n) as props
                """
            )
            nodes = []
            for rec in res_nodes:
                labels = rec["labels"]
                props = rec["props"]
                node_id = props.get("id")
                if not node_id:
                    continue
                
                # Determine type
                label = ""
                ntype = NodeType.meeting
                if "Meeting" in labels:
                    ntype = NodeType.meeting
                    label = props.get("meeting_title", node_id)
                elif "Decision" in labels:
                    ntype = NodeType.decision
                    label = props.get("text", "")[:60]
                elif "ActionItem" in labels:
                    ntype = NodeType.action_item
                    label = props.get("text", "")[:60]
                elif "Entity" in labels:
                    ntype = NodeType.entity
                    label = props.get("name", "")
                elif "Topic" in labels:
                    ntype = NodeType.topic
                    label = props.get("name", "")
                elif "Conflict" in labels:
                    # Treat conflict nodes if necessary or skip
                    continue
                
                nodes.append(GraphNode(
                    id=node_id,
                    label=label,
                    type=ntype,
                    properties=dict(props),
                ))

            # Build a set of exported node IDs so we can drop dangling edges
            # (e.g. edges that touch Conflict nodes, which are excluded above).
            exported_ids: set[str] = {n.id for n in nodes}

            # Query all relationships — exclude Conflict nodes at both ends so we
            # never return an edge whose endpoint was skipped in the nodes query.
            res_edges = session.run(
                """
                MATCH (a)-[r]->(b)
                WHERE NOT 'Conflict' IN labels(a)
                  AND NOT 'Conflict' IN labels(b)
                RETURN a.id as src, b.id as tgt, type(r) as type,
                       r.superseded as superseded, properties(r) as props
                """
            )
            edges = []
            for rec in res_edges:
                src = rec["src"]
                tgt = rec["tgt"]
                if not src or not tgt:
                    continue
                # Belt-and-suspenders: skip any edge whose endpoint isn't in the
                # exported nodes set (handles any other skipped label types).
                if src not in exported_ids or tgt not in exported_ids:
                    continue

                etype_str = rec["type"]
                # Map string to EdgeType enum safely
                try:
                    etype = EdgeType(etype_str)
                except ValueError:
                    continue

                superseded = bool(rec.get("superseded", False))
                edges.append(GraphEdge(
                    source=src,
                    target=tgt,
                    type=etype,
                    superseded=superseded,
                    properties=dict(rec.get("props") or {}),
                ))

            return GraphSnapshot(nodes=nodes, edges=edges)

    def get_status(self) -> dict[str, Any]:
        try:
            self.verify_connectivity()
            with self.driver.session() as session:
                res_nodes = session.run("MATCH (n) RETURN count(n) as count")
                node_count = res_nodes.single()["count"]
                res_edges = session.run("MATCH ()-[r]->() RETURN count(r) as count")
                edge_count = res_edges.single()["count"]
                res_dec = session.run("MATCH (d:Decision) RETURN count(d) as count")
                decision_count = res_dec.single()["count"]
                res_cf = session.run("MATCH (c:Conflict) RETURN count(c) as count")
                conflict_count = res_cf.single()["count"]
            return {
                "connected": True,
                "backend": "neo4j",
                "node_count": node_count,
                "edge_count": edge_count,
                "decision_count": decision_count,
                "conflict_count": conflict_count,
            }
        except Exception as e:
            logger.error("Neo4j health check failed: %s", e)
            return {
                "connected": False,
                "backend": "neo4j",
                "error": str(e),
            }

    def purge_person(self, person_name: str) -> dict[str, Any]:
        """Cascade-delete person entity and clear ownership from decisions and action items in Neo4j."""
        removed_entities = 0
        updated_decisions = 0
        updated_action_items = 0

        with self.driver.session() as session:
            # 1. Delete entity node and its relationships
            res_delete = session.run(
                """
                MATCH (e:Entity)
                WHERE toLower(e.name) = toLower($name)
                WITH e, count(e) as cnt
                DETACH DELETE e
                RETURN cnt
                """,
                name=person_name,
            )
            single = res_delete.single()
            if single:
                removed_entities = single["cnt"]

            # 2. Update decisions owner
            res_dec = session.run(
                """
                MATCH (d:Decision)
                WHERE toLower(d.owner) = toLower($name)
                SET d.owner = null
                RETURN count(d) as cnt
                """,
                name=person_name,
            )
            single = res_dec.single()
            if single:
                updated_decisions = single["cnt"]

            # 3. Update action items assignee
            res_ai = session.run(
                """
                MATCH (a:ActionItem)
                WHERE toLower(a.assignee) = toLower($name)
                SET a.assignee = null
                RETURN count(a) as cnt
                """,
                name=person_name,
            )
            single = res_ai.single()
            if single:
                updated_action_items = single["cnt"]

        return {
            "removed_entities": removed_entities,
            "updated_decisions": updated_decisions,
            "updated_action_items": updated_action_items,
        }

    def delete_meeting(self, meeting_id: str) -> dict[str, Any]:
        """Cascade-delete meeting and associated nodes in Neo4j."""
        deleted_decisions = 0
        deleted_action_items = 0
        deleted_conflicts = 0
        deleted_entities = 0
        deleted_topics = 0
        deleted_meetings = 0

        with self.driver.session() as session:
            # 1. Delete decisions belonging to this meeting
            res_dec = session.run(
                "MATCH (d:Decision) WHERE d.source_meeting_id = $meeting_id WITH d, count(d) as cnt DETACH DELETE d RETURN cnt",
                meeting_id=meeting_id
            )
            val = res_dec.single()
            if val:
                deleted_decisions = val["cnt"]

            # 2. Delete action items belonging to this meeting
            res_ai = session.run(
                "MATCH (a:ActionItem) WHERE a.source_meeting_id = $meeting_id WITH a, count(a) as cnt DETACH DELETE a RETURN cnt",
                meeting_id=meeting_id
            )
            val = res_ai.single()
            if val:
                deleted_action_items = val["cnt"]

            # 3. Delete conflicts belonging to this meeting
            res_cf = session.run(
                "MATCH (c:Conflict) WHERE c.meeting_a_id = $meeting_id OR c.meeting_b_id = $meeting_id OR c.resolution_meeting_id = $meeting_id WITH c, count(c) as cnt DETACH DELETE c RETURN cnt",
                meeting_id=meeting_id
            )
            val = res_cf.single()
            if val:
                deleted_conflicts = val["cnt"]

            # 4. Orphan Entity cleanup
            res_ent = session.run(
                """
                MATCH (e:Entity)-[:MENTIONED_IN]->(m:Meeting {id: $meeting_id})
                OPTIONAL MATCH (e)-[:MENTIONED_IN]->(other:Meeting)
                WHERE other.id <> $meeting_id
                WITH e, count(other) as other_count
                WHERE other_count = 0
                WITH e, count(e) as cnt
                DETACH DELETE e
                RETURN cnt
                """,
                meeting_id=meeting_id
            )
            val = res_ent.single()
            if val:
                deleted_entities = val["cnt"]

            # 5. Orphan Topic cleanup
            res_top = session.run(
                """
                MATCH (t:Topic)-[:MENTIONED_IN]->(m:Meeting {id: $meeting_id})
                OPTIONAL MATCH (t)-[:MENTIONED_IN]->(other:Meeting)
                WHERE other.id <> $meeting_id
                WITH t, count(other) as other_count
                WHERE other_count = 0
                WITH t, count(t) as cnt
                DETACH DELETE t
                RETURN cnt
                """,
                meeting_id=meeting_id
            )
            val = res_top.single()
            if val:
                deleted_topics = val["cnt"]

            # 6. Delete Meeting itself
            res_m = session.run(
                "MATCH (m:Meeting {id: $meeting_id}) WITH m, count(m) as cnt DETACH DELETE m RETURN cnt",
                meeting_id=meeting_id
            )
            val = res_m.single()
            if val:
                deleted_meetings = val["cnt"]

        return {
            "status": "success",
            "meeting_id": meeting_id,
            "deleted_decisions": deleted_decisions,
            "deleted_action_items": deleted_action_items,
            "deleted_conflicts": deleted_conflicts,
            "deleted_entities": deleted_entities,
            "deleted_topics": deleted_topics,
            "deleted_meetings": deleted_meetings,
        }

