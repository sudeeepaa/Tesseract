import React, { useState } from 'react';
import { AlertTriangle, CheckCircle2, ArrowRight, Check, Flag, Loader2 } from 'lucide-react';
import { apiClient, ConflictRecord, Decision, ResolutionChoice } from '../api/client';
import { SourceBadge } from './SourceBadge';
import { InfoTip } from './ui';
import { useToast, useAppData } from '../state/app';

const CONFIDENCE_EXPLAINER =
  'How sure the extraction agent is that these two statements truly contradict each other, ' +
  'rather than just discussing the same topic. It compares what each meeting said about the ' +
  'same decision and the specific requirement they clash on — 60%+ is escalated to you.';

interface Props {
  conflict: ConflictRecord;
  decisions: Decision[];
  onResolved?: () => void;
}

const currentUser = () => localStorage.getItem('tesseract-user') || 'You';
const short = (s: string, n = 46) => (s.length > n ? s.slice(0, n).trimEnd() + '…' : s);

export const ConflictCard: React.FC<Props> = ({ conflict, decisions, onResolved }) => {
  const { notify } = useToast();
  const { refreshConflicts } = useAppData();
  const [busy, setBusy] = useState<ResolutionChoice | null>(null);
  const [noteOpen, setNoteOpen] = useState(false);
  const [note, setNote] = useState('');

  const decisionA = decisions.find((d) => d.id === conflict.fact_a_id);
  const decisionB = decisions.find((d) => d.id === conflict.fact_b_id);
  const pct = Math.round((conflict.confidence ?? 1) * 100);

  async function resolve(choice: ResolutionChoice) {
    setBusy(choice);
    try {
      await apiClient.resolveConflict(conflict.id, {
        choice,
        note: note.trim() || undefined,
        resolved_by: currentUser(),
        keep_decision_id: decisionA?.id,
        supersede_decision_id: choice === 'switch' ? decisionA?.id : undefined,
      });
      const msg =
        choice === 'keep' ? 'Kept the current decision.'
        : choice === 'switch' ? 'Switched to the new decision.'
        : 'Flagged for review — added to your watchlist.';
      notify(msg, 'success');
      await refreshConflicts();
      onResolved?.();
    } catch (e: any) {
      notify(e.message || 'Could not save your decision.', 'error');
    } finally {
      setBusy(null);
    }
  }

  /* ── Resolved / flagged summary ─────────────────────────────────────────── */
  if (conflict.resolved) {
    const label =
      conflict.resolution_choice === 'switch' ? 'Switched to the newer decision'
      : conflict.resolution_choice === 'keep' ? 'Kept the original decision'
      : 'Resolved';
    return (
      <div className="conflict resolved">
        <div className="conflict-head">
          <span className="conflict-flag"><CheckCircle2 size={16} /> {label}</span>
          {conflict.resolved_by && (
            <span className="confidence" style={{ marginLeft: 'auto' }}>by {conflict.resolved_by}</span>
          )}
        </div>
        <div className="conflict-body">
          <div style={{ fontSize: 14.5 }}>{conflict.description}</div>
          {conflict.resolution_note && (
            <div className="conflict-reason" style={{ marginTop: 8, fontStyle: 'italic' }}>
              “{conflict.resolution_note}”
            </div>
          )}
        </div>
      </div>
    );
  }

  /* ── Active conflict — needs a human decision ───────────────────────────── */
  return (
    <div className="conflict">
      <div className="conflict-head">
        <span className="conflict-flag"><AlertTriangle size={16} /> Needs your decision</span>
        <span className="confidence" style={{ marginLeft: 'auto', gap: 6 }}>
          AI confidence
          <InfoTip text={CONFIDENCE_EXPLAINER} />
          <span className="confidence-bar"><span className="confidence-fill" style={{ width: `${pct}%` }} /></span>
          {pct}%
        </span>
      </div>

      <div className="conflict-body">
        <div className="conflict-q">Should this decision still stand?</div>
        <div className="conflict-reason">{conflict.description}</div>

        <div className="conflict-vs">
          <div className="conflict-side">
            <div className="side-tag">Current decision</div>
            <div className="side-text">{conflict.fact_a_text || decisionA?.text}</div>
            <SourceBadge meetingId={conflict.meeting_a_id} />
          </div>
          <span className="vs">clashes with</span>
          <div className="conflict-side">
            <div className="side-tag">Raised later</div>
            <div className="side-text">{conflict.fact_b_text}</div>
            <SourceBadge meetingId={conflict.meeting_b_id} />
          </div>
        </div>

        {conflict.reasoning && (
          <div className="conflict-reason" style={{ marginBottom: 14 }}>
            <strong style={{ fontWeight: 600 }}>Why it was flagged: </strong>{conflict.reasoning}
          </div>
        )}

        {!noteOpen ? (
          <div className="conflict-actions">
            <button className="btn btn-outline btn-sm" disabled={!!busy} onClick={() => resolve('keep')}>
              {busy === 'keep' ? <Loader2 size={15} className="spin" /> : <Check size={15} />}
              Keep {decisionA ? `“${short(decisionA.text, 26)}”` : 'this decision'}
            </button>

            {decisionB && (
              <button className="btn btn-primary btn-sm" disabled={!!busy} onClick={() => resolve('switch')}>
                {busy === 'switch' ? <Loader2 size={15} className="spin" /> : <ArrowRight size={15} />}
                Switch to “{short(decisionB.text, 26)}”
              </button>
            )}

            <button className="btn btn-ghost btn-sm" disabled={!!busy} onClick={() => setNoteOpen(true)}>
              <Flag size={15} /> Flag for review
            </button>
          </div>
        ) : (
          <div className="stack-sm">
            <textarea
              className="textarea"
              placeholder="Add a note for your team (optional) — e.g. “Ask legal to confirm before we change anything.”"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              autoFocus
            />
            <div className="conflict-actions">
              <button className="btn btn-primary btn-sm" disabled={busy === 'review'} onClick={() => resolve('review')}>
                {busy === 'review' ? <Loader2 size={15} className="spin" /> : <Flag size={15} />}
                Flag for review
              </button>
              <button className="btn btn-ghost btn-sm" disabled={!!busy} onClick={() => { setNoteOpen(false); setNote(''); }}>
                Cancel
              </button>
              <span className="muted" style={{ fontSize: 12.5 }}>Keeps this on your watchlist and marks the decision “under review”.</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
