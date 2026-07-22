import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ListTodo, User, CalendarClock, Sparkles } from 'lucide-react';
import { apiClient, BriefingOutput, ActionItem } from '../api/client';
import { StatusPill, EmptyState, SkeletonLines } from '../components/ui';
import { SourceBadge } from '../components/SourceBadge';

const Row: React.FC<{ a: ActionItem }> = ({ a }) => (
  <div className="between" style={{ padding: '13px 16px', gap: 12, borderTop: '1px solid var(--border)' }}>
    <div className="grow">
      <div style={{ fontWeight: 550, fontSize: 14.5, textDecoration: a.status === 'completed' || a.status === 'cancelled' ? 'line-through' : 'none', opacity: a.status === 'completed' || a.status === 'cancelled' ? 0.7 : 1 }}>
        {a.text}
      </div>
      <div className="row wrap" style={{ gap: 14, marginTop: 5 }}>
        {a.assignee && <span className="muted row" style={{ gap: 4, fontSize: 12.5 }}><User size={12} />{a.assignee}</span>}
        {a.due_date && a.due_date !== 'null' && <span className="muted row" style={{ gap: 4, fontSize: 12.5 }}><CalendarClock size={12} />{a.due_date}</span>}
      </div>
    </div>
    <div className="row" style={{ gap: 8, flex: 'none' }}>
      <StatusPill value={a.status} kind="action" />
      <SourceBadge meetingId={a.source_meeting_id} />
    </div>
  </div>
);

export const ActionItemsView: React.FC = () => {
  const [briefing, setBriefing] = useState<BriefingOutput | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try { setBriefing(await apiClient.getBriefing()); } catch { /* */ } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);

  const open = briefing?.action_items.filter((a) => a.status === 'open' || a.status === 'in_progress') ?? [];
  const done = briefing?.action_items.filter((a) => a.status === 'completed' || a.status === 'cancelled') ?? [];

  return (
    <div className="page stack-lg">
      <header>
        <div className="page-eyebrow">Action items</div>
        <h1 className="page-title">Who owes what</h1>
        <p className="page-lead">Every task and owner Tesseract heard across your meetings.</p>
      </header>

      {loading && <SkeletonLines rows={5} />}

      {!loading && briefing && briefing.action_items.length === 0 && (
        <EmptyState icon={<ListTodo size={22} />} title="No action items yet"
          children={<>When people commit to tasks in a meeting, they’ll show up here with an owner and due date.</>}
          action={<Link to="/add" className="btn btn-primary btn-sm"><Sparkles size={15} /> Add a meeting</Link>} />
      )}

      {!loading && open.length > 0 && (
        <section>
          <div className="section-title">Open · {open.length}</div>
          <div className="card">{open.map((a) => <Row key={a.id} a={a} />)}</div>
        </section>
      )}
      {!loading && done.length > 0 && (
        <section>
          <div className="section-title">Done &amp; cancelled · {done.length}</div>
          <div className="card">{done.map((a) => <Row key={a.id} a={a} />)}</div>
        </section>
      )}
    </div>
  );
};
