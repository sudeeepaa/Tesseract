import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ClipboardCheck, Sparkles, ChevronDown, ArrowRightLeft, AlertTriangle, ShieldCheck, Check, X, MessageSquarePlus, Loader2, UserCheck } from 'lucide-react';
import { apiClient, BriefingOutput, ConflictRecord, Decision, MeetingSummary, DecisionReviewAction } from '../api/client';
import { StatusPill, EmptyState, SkeletonLines, InfoTip } from '../components/ui';
import { meetingLabel } from '../components/SourceBadge';
import { useToast } from '../state/app';

const currentUser = () => localStorage.getItem('tesseract-user') || 'You';

const WHY_CHANGED_EXPLAINER =
  "Captured from the meeting where this decision's status changed — the model's stated reason " +
  'for moving it to under review, replacing it, or reversing it.';
const CONFLICT_CONFIDENCE_EXPLAINER =
  'How sure the extraction agent is that these two statements truly contradict each other, based ' +
  'on whether they name the same decision and the same clashing requirement.';

function fmtDate(iso?: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function confidenceColor(score: number): string {
  if (score >= 0.8) return 'var(--red)';
  if (score >= 0.6) return 'var(--amber)';
  return 'var(--green)';
}

const DecisionRow: React.FC<{ d: Decision; conflicts: ConflictRecord[]; onChanged: () => void }> = ({ d, conflicts, onChanged }) => {
  const { notify } = useToast();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<DecisionReviewAction | null>(null);
  const [commentOpen, setCommentOpen] = useState(false);
  const [comment, setComment] = useState('');
  const muted = d.status === 'superseded' || d.status === 'reversed';
  const changed = d.status === 'superseded' || d.status === 'reversed' || d.status === 'under_review';
  const hasDetail = !!(d.rationale || d.owner || d.supersedes_decision_id || (changed && d.status_reason) ||
    (d.contradicts_decision_ids && d.contradicts_decision_ids.length));

  async function review(action: DecisionReviewAction) {
    setBusy(action);
    try {
      await apiClient.reviewDecision(d.id, {
        action,
        note: comment.trim() || undefined,
        reviewed_by: currentUser(),
      });
      notify(
        action === 'approve' ? 'Decision approved.'
        : action === 'reject' ? 'Decision rejected.'
        : 'Comment saved.',
        'success'
      );
      setComment('');
      setCommentOpen(false);
      onChanged();
    } catch (e: any) {
      notify(e.message || 'Could not save your review.', 'error');
    } finally {
      setBusy(null);
    }
  }

  const relatedConflicts = conflicts.filter(
    (c) => c.fact_a_id === d.id || c.fact_b_id === d.id ||
           (d.contradicts_decision_ids ?? []).includes(c.fact_a_id) ||
           (d.contradicts_decision_ids ?? []).includes(c.fact_b_id)
  );

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

          {changed && d.status_reason && (
            <div style={{ marginTop: 4, borderTop: '1px solid var(--border)', paddingTop: 10 }} className="stack-sm">
              <div className="row" style={{ gap: 6, marginBottom: 4 }}>
                <ShieldCheck size={13} color="var(--accent)" />
                <span style={{ fontSize: 11.5, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Why this changed</span>
                <InfoTip text={WHY_CHANGED_EXPLAINER} />
              </div>
              <div style={{ fontSize: 13.5, lineHeight: 1.55, color: 'var(--text-2)', fontStyle: 'italic' }}>
                "{d.status_reason}"
              </div>
            </div>
          )}

          {relatedConflicts.length > 0 && (
            <div style={{ marginTop: 4, borderTop: '1px solid var(--border)', paddingTop: 10 }} className="stack-sm">
              <div className="row" style={{ gap: 6, marginBottom: 4 }}>
                <ShieldCheck size={13} color="var(--accent)" />
                <span style={{ fontSize: 11.5, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Explainability</span>
              </div>
              {relatedConflicts.map((c) => (
                <div key={c.id} style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 7, padding: '9px 11px' }} className="stack-sm">
                  {c.confidence != null && (
                    <div className="row" style={{ gap: 8, alignItems: 'center' }}>
                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Conflict confidence</span>
                      <InfoTip text={CONFLICT_CONFIDENCE_EXPLAINER} />
                      <span style={{
                        fontSize: 12.5, fontWeight: 700,
                        color: confidenceColor(c.confidence),
                        background: `color-mix(in srgb, ${confidenceColor(c.confidence)} 14%, transparent)`,
                        padding: '1px 7px', borderRadius: 20,
                      }}>{Math.round(c.confidence * 100)}%</span>
                      {c.confidence >= 0.6 && <span style={{ fontSize: 11, color: 'var(--amber)' }}>⚠ Escalated</span>}
                    </div>
                  )}
                  {c.reasoning && (
                    <div style={{ fontSize: 13, lineHeight: 1.55, color: 'var(--text-2)', fontStyle: 'italic' }}>
                      "{c.reasoning}"
                    </div>
                  )}
                  {!c.reasoning && !c.confidence && (
                    <div className="muted" style={{ fontSize: 12.5 }}>{c.description}</div>
                  )}
                </div>
              ))}
            </div>
          )}

          {!hasDetail && relatedConflicts.length === 0 && <div className="muted" style={{ fontSize: 13 }}>No additional details were captured for this decision.</div>}

          {/* ── Human review ─────────────────────────────────────────────── */}
          {d.review_note && (
            <div style={{ marginTop: 4, borderTop: '1px solid var(--border)', paddingTop: 10 }} className="stack-sm">
              <div className="row" style={{ gap: 6, marginBottom: 2 }}>
                <UserCheck size={13} color="var(--accent)" />
                <span style={{ fontSize: 11.5, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                  Your team's note{d.reviewed_by ? ` · ${d.reviewed_by}` : ''}
                </span>
              </div>
              <div style={{ fontSize: 13.5, lineHeight: 1.55, color: 'var(--text-2)', fontStyle: 'italic' }}>"{d.review_note}"</div>
            </div>
          )}

          <div style={{ marginTop: 4, borderTop: '1px solid var(--border)', paddingTop: 12 }} className="stack-sm">
            <div style={{ fontSize: 11.5, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Your review</div>
            {!commentOpen ? (
              <div className="row wrap" style={{ gap: 8 }}>
                <button className="btn btn-outline btn-sm" disabled={!!busy} onClick={() => review('approve')}>
                  {busy === 'approve' ? <Loader2 size={15} className="spin" /> : <Check size={15} />} Approve
                </button>
                <button className="btn btn-outline btn-sm" disabled={!!busy} onClick={() => review('reject')}>
                  {busy === 'reject' ? <Loader2 size={15} className="spin" /> : <X size={15} />} Reject
                </button>
                <button className="btn btn-ghost btn-sm" disabled={!!busy} onClick={() => setCommentOpen(true)}>
                  <MessageSquarePlus size={15} /> Comment
                </button>
              </div>
            ) : (
              <div className="stack-sm">
                <textarea
                  className="textarea"
                  placeholder="Add a note for your team — e.g. “Confirmed with legal, this is fine to keep.”"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  autoFocus
                />
                <div className="row wrap" style={{ gap: 8, alignItems: 'center' }}>
                  <button className="btn btn-primary btn-sm" disabled={busy === 'comment' || !comment.trim()} onClick={() => review('comment')}>
                    {busy === 'comment' ? <Loader2 size={15} className="spin" /> : <MessageSquarePlus size={15} />} Save comment
                  </button>
                  <button className="btn btn-ghost btn-sm" disabled={!!busy} onClick={() => { setCommentOpen(false); setComment(''); }}>Cancel</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export const DecisionsView: React.FC = () => {
  const [briefing, setBriefing] = useState<BriefingOutput | null>(null);
  const [meetings, setMeetings] = useState<MeetingSummary[]>([]);
  const [conflicts, setConflicts] = useState<ConflictRecord[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [b, m, cr] = await Promise.all([
        apiClient.getBriefing(),
        apiClient.listMeetings(),
        apiClient.listConflicts(),
      ]);
      setBriefing(b);
      setMeetings(m.meetings);
      setConflicts(cr.conflicts);
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
              {items.map((d) => <DecisionRow key={d.id} d={d} conflicts={conflicts} onChanged={load} />)}
            </div>
          </section>
        );
      })}
    </div>
  );
};
