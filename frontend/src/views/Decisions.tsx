import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ClipboardCheck, Sparkles } from 'lucide-react';
import { apiClient, BriefingOutput, Decision } from '../api/client';
import { StatusPill, EmptyState, SkeletonLines } from '../components/ui';
import { SourceBadge } from '../components/SourceBadge';

const DecisionRow: React.FC<{ d: Decision; muted?: boolean }> = ({ d, muted }) => (
  <div className="card card-pad" style={{ opacity: muted ? 0.75 : 1 }}>
    <div className="between" style={{ alignItems: 'flex-start', gap: 12 }}>
      <div className="grow">
        <div style={{ fontWeight: 600, fontSize: 15, textDecoration: muted ? 'line-through' : 'none' }}>{d.text}</div>
        {d.rationale && (
          <div className="text-2" style={{ fontSize: 13.5, marginTop: 6, paddingLeft: 10, borderLeft: '2px solid var(--border-strong)' }}>
            {d.rationale}
          </div>
        )}
        {d.owner && <div className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>Owner · {d.owner}</div>}
      </div>
      <div className="row" style={{ gap: 8, flex: 'none' }}>
        <StatusPill value={d.status} />
        <SourceBadge meetingId={d.source_meeting_id} />
      </div>
    </div>
  </div>
);

const Group: React.FC<{ title: string; note?: string; items: Decision[]; muted?: boolean }> = ({ title, note, items, muted }) =>
  items.length === 0 ? null : (
    <section>
      <div className="section-title" style={{ marginBottom: 4 }}>{title} · {items.length}</div>
      {note && <div className="muted" style={{ fontSize: 13, marginBottom: 10 }}>{note}</div>}
      <div className="stack-sm" style={{ marginTop: note ? 0 : 10 }}>
        {items.map((d) => <DecisionRow key={d.id} d={d} muted={muted} />)}
      </div>
    </section>
  );

export const DecisionsView: React.FC = () => {
  const [briefing, setBriefing] = useState<BriefingOutput | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try { setBriefing(await apiClient.getBriefing()); } catch { /* */ } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);

  const confirmed = briefing?.decisions.filter((d) => d.status === 'confirmed') ?? [];
  const review = briefing?.decisions.filter((d) => d.status === 'under_review') ?? [];
  const replaced = briefing?.decisions.filter((d) => d.status === 'superseded' || d.status === 'reversed') ?? [];

  return (
    <div className="page stack-lg">
      <header>
        <div className="page-eyebrow">Decisions</div>
        <h1 className="page-title">What your team has decided</h1>
        <p className="page-lead">Every decision captured across your meetings, and how it has changed over time.</p>
      </header>

      {loading && <SkeletonLines rows={5} />}

      {!loading && briefing && briefing.decisions.length === 0 && (
        <EmptyState icon={<ClipboardCheck size={22} />} title="No decisions captured yet"
          children={<>Add a meeting and Tesseract will pull out the decisions automatically.</>}
          action={<Link to="/add" className="btn btn-primary btn-sm"><Sparkles size={15} /> Add a meeting</Link>} />
      )}

      {!loading && briefing && briefing.decisions.length > 0 && (
        <>
          <Group title="Confirmed" items={confirmed} />
          <Group title="Under review" note="Flagged as uncertain — a replacement hasn’t been chosen yet." items={review} />
          <Group title="Replaced" note="Superseded by a newer decision. Kept for history." items={replaced} muted />
        </>
      )}
    </div>
  );
};
