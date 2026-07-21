import React from 'react';
import { Loader2 } from 'lucide-react';

/* ── Status pill ──────────────────────────────────────────────────────────── */
type Tone = 'green' | 'amber' | 'red' | 'blue' | 'gray';

const DECISION_TONE: Record<string, [Tone, string]> = {
  confirmed:    ['green', 'Confirmed'],
  proposed:     ['blue',  'Proposed'],
  under_review: ['amber', 'Under review'],
  superseded:   ['gray',  'Replaced'],
  reversed:     ['gray',  'Reversed'],
};
const ACTION_TONE: Record<string, [Tone, string]> = {
  open:        ['blue',  'Open'],
  in_progress: ['amber', 'In progress'],
  completed:   ['green', 'Done'],
  cancelled:   ['gray',  'Cancelled'],
};

export const StatusPill: React.FC<{ value: string; kind?: 'decision' | 'action' }> = ({ value, kind = 'decision' }) => {
  const map = kind === 'action' ? ACTION_TONE : DECISION_TONE;
  const [tone, label] = map[value] ?? (['gray', value] as [Tone, string]);
  return <span className={`pill pill-${tone}`}>{label}</span>;
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
