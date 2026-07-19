"""
Threadline briefing generator.

Pure function: receives pre-fetched lists from the graph store,
produces BriefingOutput (structured dict + Markdown).
No store dependencies — the Pipeline queries the stores and passes data in.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from threadline.models import (
    ActionItem,
    ActionItemStatus,
    BriefingOutput,
    ConflictRecord,
    Decision,
    DecisionStatus,
)

logger = logging.getLogger(__name__)


class BriefingGenerator:
    """
    Generates a BriefingOutput from all known decisions, action items,
    conflicts, and topics.
    """

    def generate(
        self,
        all_decisions:    list[Decision],
        all_action_items: list[ActionItem],
        all_conflicts:    list[ConflictRecord],
        all_topics:       list[str],
        meeting_count:    int,
    ) -> BriefingOutput:
        markdown = self._render_markdown(
            all_decisions, all_action_items, all_conflicts, all_topics, meeting_count
        )
        return BriefingOutput(
            generated_at=datetime.now(timezone.utc),
            meeting_count=meeting_count,
            decisions=all_decisions,
            action_items=all_action_items,
            conflicts=all_conflicts,
            topics=all_topics,
            markdown=markdown,
        )

    # ── Markdown rendering ────────────────────────────────────────────────────

    def _render_markdown(
        self,
        decisions:    list[Decision],
        action_items: list[ActionItem],
        conflicts:    list[ConflictRecord],
        topics:       list[str],
        meeting_count: int,
    ) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        L: list[str] = [
            "# Threadline — Executive Briefing",
            "",
            f"_Generated: {ts} · {meeting_count} meeting(s) processed_",
            "",
        ]

        # ── Bucket decisions by status ────────────────────────────────────────
        active      = [d for d in decisions if d.status == DecisionStatus.confirmed]
        proposed    = [d for d in decisions if d.status == DecisionStatus.proposed]
        under_rev   = [d for d in decisions if d.status == DecisionStatus.under_review]
        superseded  = [d for d in decisions if d.status == DecisionStatus.superseded]
        reversed_d  = [d for d in decisions if d.status == DecisionStatus.reversed]

        # ── Active decisions ──────────────────────────────────────────────────
        L += ["## ✅ Confirmed Decisions", ""]
        if active:
            for d in active:
                owner = f" _(owner: {d.owner})_" if d.owner else ""
                L.append(f"- **{d.text}**{owner} `[{d.source_meeting_id}]`")
                if d.rationale:
                    L.append(f"  > {d.rationale}")
        else:
            L.append("_No confirmed decisions yet._")
        L.append("")

        # ── Proposed ─────────────────────────────────────────────────────────
        if proposed:
            L += ["## 💡 Proposed (not yet confirmed)", ""]
            for d in proposed:
                L.append(f"- {d.text} `[{d.source_meeting_id}]`")
            L.append("")

        # ── Under review — DISTINCT from superseded ───────────────────────────
        if under_rev:
            L += ["## ⚠️ Decisions Under Review", ""]
            L.append(
                "> These decisions are being evaluated for problems "
                "but have NOT been replaced yet."
            )
            L.append("")
            for d in under_rev:
                L.append(f"- ~~{d.text}~~ — **under review** `[{d.source_meeting_id}]`")
            L.append("")

        # ── Conflicts ─────────────────────────────────────────────────────────
        open_conflicts     = [c for c in conflicts if not c.resolved]
        resolved_conflicts = [c for c in conflicts if c.resolved]

        if open_conflicts:
            L += ["## 🔴 Open Conflicts", ""]
            for c in open_conflicts:
                L.append(f"- **{c.description}**")
                L.append(f"  - `{c.meeting_a_id}` said: _{c.fact_a_text}_")
                L.append(f"  - `{c.meeting_b_id}` raised: _{c.fact_b_text}_")
            L.append("")

        if resolved_conflicts:
            L += ["## ✅ Resolved Conflicts", ""]
            for c in resolved_conflicts:
                L.append(f"- ~~{c.description}~~ _(resolved in {c.resolution_meeting_id})_")
            L.append("")

        # ── Decision history ──────────────────────────────────────────────────
        if superseded or reversed_d:
            L += ["## 📜 Decision History", ""]
            for d in superseded:
                L.append(f"- ~~{d.text}~~ — **superseded** `[{d.source_meeting_id}]`")
            for d in reversed_d:
                L.append(f"- ~~{d.text}~~ — **reversed** `[{d.source_meeting_id}]`")
            L.append("")

        # ── Action items ──────────────────────────────────────────────────────
        open_ai = [a for a in action_items
                   if a.status in (ActionItemStatus.open, ActionItemStatus.in_progress)]
        done_ai = [a for a in action_items if a.status == ActionItemStatus.completed]

        L += ["## 📋 Open Action Items", ""]
        if open_ai:
            for a in open_ai:
                assignee = f" → **{a.assignee}**" if a.assignee else ""
                due      = f" (due {a.due_date})" if a.due_date else ""
                stale_str = ""
                if getattr(a, "is_stale", False):
                    stale_str = f" ⚠️ **[STALE]** (Confidence: {a.confidence:.2f}, Reasoning: {a.reasoning})"
                L.append(f"- [ ] {a.text}{assignee}{due}{stale_str} `[{a.source_meeting_id}]`")
        else:
            L.append("_No open action items._")
        L.append("")

        if done_ai:
            L += ["## ✔️ Completed", ""]
            for a in done_ai:
                L.append(f"- [x] {a.text}")
            L.append("")

        # ── Topics ────────────────────────────────────────────────────────────
        if topics:
            L += ["## 🏷️ Topics", ""]
            L.append(", ".join(f"`{t}`" for t in sorted(set(topics))))
            L.append("")

        return "\n".join(L)
