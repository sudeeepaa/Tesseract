import React from 'react';
import { useAppData } from '../state/app';

/**
 * Plain-language health for a non-technical user. The underlying Neo4j/Qdrant/
 * LLM details live in Settings; here we only say whether the assistant's memory
 * is fully connected, running in local demo mode, or offline.
 */
export const SystemStatus: React.FC<{ compact?: boolean }> = ({ compact }) => {
  const { status, online } = useAppData();

  let tone: 'green' | 'amber' | 'red' = 'green';
  let label = 'Memory connected';
  let color = 'var(--green)';

  if (!online || !status) {
    tone = 'red'; label = "Can't reach assistant"; color = 'var(--red)';
  } else {
    const demo = status.neo4j.backend === 'memory' || status.qdrant.backend === 'memory';
    if (demo) { tone = 'amber'; label = 'Local demo mode'; color = 'var(--amber)'; }
  }

  return (
    <div className="col" style={{ gap: 6 }}>
      <div className="row" title={
        !online ? 'The backend is not responding.'
        : tone === 'amber' ? 'Running with in-memory storage — great for demos, not saved permanently.'
        : 'Connected to persistent memory (Qdrant + graph).'
      }>
        <span className="dot" style={{ background: color, boxShadow: `0 0 0 3px color-mix(in srgb, ${color} 18%, transparent)` }} />
        <span style={{ fontSize: 13, color: 'var(--text-2)', fontWeight: 500 }}>{label}</span>
      </div>
      {!compact && (
        <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>Powered by Qdrant&nbsp;+&nbsp;Lyzr</div>
      )}
    </div>
  );
};
