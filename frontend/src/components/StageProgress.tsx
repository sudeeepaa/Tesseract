import React from 'react';
import { Loader2, CheckCircle2, XCircle, Circle, MinusCircle } from 'lucide-react';
import { PipelineStageEvent } from '../api/client';

type Stage = 'INGEST' | 'TRANSCRIBE' | 'EXTRACT' | 'GRAPH_WRITE' | 'VECTOR_WRITE' | 'BRIEFING';

const STAGES: { key: Stage; label: string }[] = [
  { key: 'INGEST',       label: 'Reading the meeting' },
  { key: 'TRANSCRIBE',   label: 'Transcribing audio' },
  { key: 'EXTRACT',      label: 'Finding decisions & tasks' },
  { key: 'GRAPH_WRITE',  label: 'Saving to memory' },
  { key: 'VECTOR_WRITE', label: 'Indexing for search' },
  { key: 'BRIEFING',     label: 'Updating your briefing' },
];

const icon = (status: string) => {
  switch (status) {
    case 'running': return <Loader2 size={18} className="spin" color="var(--accent)" />;
    case 'done':    return <CheckCircle2 size={18} color="var(--green)" />;
    case 'error':   return <XCircle size={18} color="var(--red)" />;
    case 'skipped': return <MinusCircle size={18} color="var(--text-muted)" />;
    default:        return <Circle size={18} color="var(--border-strong)" />;
  }
};

export const StageProgress: React.FC<{ events: PipelineStageEvent[] }> = ({ events }) => {
  const statusFor = (s: Stage) =>
    [...events].reverse().find((e) => e.stage === s)?.status || 'pending';
  const msgFor = (s: Stage) =>
    [...events].reverse().find((e) => e.stage === s)?.message || '';

  return (
    <div className="col" style={{ gap: 4 }}>
      {STAGES.map(({ key, label }) => {
        const status = statusFor(key);
        const running = status === 'running';
        return (
          <div key={key} className="row" style={{
            gap: 11, padding: '9px 11px', borderRadius: 'var(--r-sm)',
            background: running ? 'var(--accent-soft)' : 'transparent',
            opacity: status === 'pending' ? 0.55 : 1,
          }}>
            {icon(status)}
            <div className="grow">
              <div style={{ fontSize: 14, fontWeight: running ? 600 : 500 }}>{label}</div>
              {msgFor(key) && status !== 'pending' && (
                <div className="muted" style={{ fontSize: 12.5 }}>{msgFor(key)}</div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};
