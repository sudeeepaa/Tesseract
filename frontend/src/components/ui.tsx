import React from 'react';
import { Loader2, Info } from 'lucide-react';

/* ── Info tooltip ─────────────────────────────────────────────────────────── */
/** A small "i" icon that shows a plain-language explanation on hover/focus.
 *  Use wherever a number, status, or term needs one extra sentence of context
 *  to be self-explanatory to a non-technical reader. */
export const InfoTip: React.FC<{ text: string; size?: number; placement?: 'top' | 'bottom'; align?: 'center' | 'end' }> =
  ({ text, size = 13, placement = 'top', align = 'center' }) => (
    <span
      className={`info-tip${placement === 'bottom' ? ' info-tip-below' : ''}${align === 'end' ? ' info-tip-end' : ''}`}
      tabIndex={0} data-tip={text} aria-label={text} style={{ verticalAlign: 'middle' }}
    >
      <Info size={size} />
    </span>
  );

/* ── Status pill ──────────────────────────────────────────────────────────── */
type Tone = 'green' | 'amber' | 'red' | 'blue' | 'gray';

const DECISION_TONE: Record<string, [Tone, string, string]> = {
  confirmed:    ['green', 'Confirmed', 'The team agreed on this and no concern has been raised since.'],
  proposed:     ['blue',  'Proposed', 'Mentioned as an option in a meeting, but not yet agreed upon.'],
  under_review: ['amber', 'Under review', 'A later meeting raised a concern about this decision, but no replacement has been confirmed yet — it is still nominally in force.'],
  superseded:   ['gray',  'Replaced', 'A later meeting explicitly replaced this with a new, confirmed decision.'],
  reversed:     ['gray',  'Reversed', 'A later meeting cancelled this decision with no replacement chosen.'],
};
const ACTION_TONE: Record<string, [Tone, string, string]> = {
  open:        ['blue',  'Open', 'Assigned but not yet started or completed.'],
  in_progress: ['amber', 'In progress', 'Work on this task has started.'],
  completed:   ['green', 'Done', 'This task was marked complete.'],
  cancelled:   ['gray',  'Cancelled', 'This task was called off before completion.'],
};

export const StatusPill: React.FC<{ value: string; kind?: 'decision' | 'action' }> = ({ value, kind = 'decision' }) => {
  const map = kind === 'action' ? ACTION_TONE : DECISION_TONE;
  const [tone, label, explain] = map[value] ?? (['gray', value, ''] as [Tone, string, string]);
  return (
    <span className={`pill pill-${tone}`} tabIndex={explain ? 0 : undefined} data-tip={explain || undefined} style={{ cursor: explain ? 'help' : undefined }}>
      {label}
    </span>
  );
};

/* ── Stat card ────────────────────────────────────────────────────────────── */
export const StatCard: React.FC<{ value: React.ReactNode; label: string; icon?: React.ReactNode; accent?: string }> =
({ value, label, icon, accent }) => (
  <div className="card stat">
    <div className="stat-num" style={accent ? { color: accent } : undefined}>{value}</div>
    <div className="stat-label">{icon}{label}</div>
  </div>
);

/* ── Empty state ──────────────────────────────────────────────────────────── */
export const EmptyState: React.FC<{ icon?: React.ReactNode; title: string; children?: React.ReactNode; action?: React.ReactNode }> =
({ icon, title, children, action }) => (
  <div className="card"><div className="empty">
    {icon && <div className="empty-icon">{icon}</div>}
    <div style={{ fontWeight: 600, color: 'var(--text)', fontSize: 15 }}>{title}</div>
    {children && <div style={{ marginTop: 6, maxWidth: 380, marginInline: 'auto' }}>{children}</div>}
    {action && <div style={{ marginTop: 16 }}>{action}</div>}
  </div></div>
);

/* ── Skeleton ─────────────────────────────────────────────────────────────── */
export const SkeletonLines: React.FC<{ rows?: number }> = ({ rows = 3 }) => (
  <div className="card card-pad stack-sm">
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="skeleton" style={{ height: 16, width: `${90 - i * 12}%` }} />
    ))}
  </div>
);

/* ── Confirm dialog ───────────────────────────────────────────────────────── */
export const ConfirmDialog: React.FC<{
  open: boolean; title: string; message: React.ReactNode; confirmLabel?: string;
  danger?: boolean; busy?: boolean; onConfirm: () => void; onCancel: () => void;
}> = ({ open, title, message, confirmLabel = 'Confirm', danger, busy, onConfirm, onCancel }) => {
  if (!open) return null;
  return (
    <div className="overlay" onClick={onCancel}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <h3 style={{ fontSize: 17, marginBottom: 8 }}>{title}</h3>
        <div className="text-2" style={{ fontSize: 14, marginBottom: 18 }}>{message}</div>
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <button className="btn btn-ghost btn-sm" onClick={onCancel} disabled={busy}>Cancel</button>
          <button className={`btn btn-sm ${danger ? 'btn-danger' : 'btn-primary'}`} onClick={onConfirm} disabled={busy}>
            {busy && <Loader2 size={15} className="spin" />}{confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};
