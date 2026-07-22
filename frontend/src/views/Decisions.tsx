import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ClipboardCheck, Sparkles, ChevronDown, ArrowRightLeft, AlertTriangle } from 'lucide-react';
import { apiClient, BriefingOutput, Decision, MeetingSummary } from '../api/client';
import { StatusPill, EmptyState, SkeletonLines } from '../components/ui';
import { meetingLabel } from '../components/SourceBadge';

function fmtDate(iso?: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

const DecisionRow: React.FC<{ d: Decision }> = ({ d }) => {
  const [open, setOpen] = useState(false);
  const muted = d.status === 'superseded' || d.status === 'reversed';
  const hasDetail = !!(d.rationale || d.owner || d.supersedes_decision_id ||
    (d.contradicts_decision_ids && d.contradicts_decision_ids.length));

  return (
    <div className="card card-pad" style={{ opacity: muted ? 0.78 : 1 }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{ all: 'unset', cursor: 'pointer', display: 'block', width: '100%' }}
        aria-expanded={open}
      >
        <div className="between" style={{ alignItems: 'flex-start', gap: 12 }}>
          <div className="grow" style={{ fontWeight: 600, fontSize: 15, textDecoration: muted ? 'line-through' : 'none' }}>
            {d.text}
          </div>
          <div className="row" style={{ gap: 8, flex: 'none', alignItems: 'center' }}>
            <StatusPill value={d.status} />
            <ChevronDown size={16} color="var(--text-muted)"
              style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .15s' }} />
          </div>
        </div>
      </button>

      {open && (
        <div style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 12 }} className="stack-sm">
          {d.rationale ? (
            <div>
              <div className="detail-label">Why</div>
              <div style={{ fontSize: 14, lineHeight: 1.5 }}>{d.rationale}</div>
            </div>
          ) : null}
          {d.owner && (
            <div><span className="detail-label">Owner</span><span style={{ fontSize: 14 }}>{d.owner}</span></div>
          )}
          {d.supersedes_decision_id && (
            <div className="row" style={{ gap: 7, fontSize: 13.5, color: 'var(--text-2)' }}>
              <ArrowRightLeft size={14} /> Replaces an earlier decision
            </div>
          )}
          {d.contradicts_decision_ids && d.contradicts_decision_ids.length > 0 && (
            <div className="row" style={{ gap: 7, fontSize: 13.5, color: 'var(--amber)' }}>
              <AlertTriangle size={14} /> Conflicts with {d.contradicts_decision_ids.length} other decision{d.contradicts_decision_ids.length === 1 ? '' : 's'}
            </div>
          )}
          {!hasDetail && <div className="muted" style={{ fontSize: 13 }}>No additional details were captured for this decision.</div>}
        </div>
      )}
    </div>
  );
};

export const DecisionsView: React.FC = () => {
  const [briefing, setBriefing] = useState<BriefingOutput | null>(null);
  const [meetings, setMeetings] = useState<MeetingSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [b, m] = await Promise.all([apiClient.getBriefing(), apiClient.listMeetings()]);
      setBriefing(b);
      setMeetings(m.meetings);
    } catch { /* */ } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);

  const decisions = briefing?.decisions ?? [];

  // Group decisions by meeting, ordered by the chronological meetings list.
  const byMeeting = new Map<string, Decision[]>();
  for (const d of decisions) {
    const arr = byMeeting.get(d.source_meeting_id) ?? [];
    arr.push(d);
    byMeeting.set(d.source_meeting_id, arr);
  }
  const order = meetings.map((m) => m.id);
  const orderedIds = [
    ...order.filter((id) => byMeeting.has(id)),
    ...[...byMeeting.keys()].filter((id) => !order.includes(id)),
  ];
  const dateOf = (id: string) => {
    const m = meetings.find((x) => x.id === id);
    return m ? fmtDate(m.recorded_at) || fmtDate(m.ingested_at) : null;
  };

  return (
    <div className="page stack-lg">
      <header>
        <div className="page-eyebrow">Decisions</div>
        <h1 className="page-title">What your team has decided</h1>
        <p className="page-lead">Grouped by meeting, in the order they happened. Tap any decision for the details.</p>
      </header>

      {loading && <SkeletonLines rows={5} />}

      {!loading && decisions.length === 0 && (
        <EmptyState icon={<ClipboardCheck size={22} />} title="No decisions captured yet"
          children={<>Add a meeting and Tesseract will pull out the decisions automatically.</>}
          action={<Link to="/add" className="btn btn-primary btn-sm"><Sparkles size={15} /> Add a meeting</Link>} />
      )}

      {!loading && decisions.length > 0 && orderedIds.map((mid) => {
        const items = byMeeting.get(mid) ?? [];
        const date = dateOf(mid);
        return (
          <section key={mid}>
            <div className="between" style={{ marginBottom: 10, alignItems: 'baseline' }}>
              <div className="section-title">{meetingLabel(mid)} · {items.length}</div>
              {date && <span className="muted" style={{ fontSize: 12.5 }}>{date}</span>}
            </div>
            <div className="stack-sm">
              {items.map((d) => <DecisionRow key={d.id} d={d} />)}
            </div>
          </section>
        );
      })}
    </div>
  );
};
