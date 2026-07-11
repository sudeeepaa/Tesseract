import React from 'react';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';
import { ConflictRecord } from '../api/client';
import { SourceBadge } from './SourceBadge';

interface ConflictAlertProps {
  conflict: ConflictRecord;
}

export const ConflictAlert: React.FC<ConflictAlertProps> = ({ conflict }) => {
  return (
    <div 
      className="glass-panel"
      style={{
        padding: '1.25rem',
        borderRadius: 'var(--radius-md)',
        borderLeft: `4px solid ${conflict.resolved ? 'var(--color-success)' : 'var(--color-warning)'}`,
        backgroundColor: conflict.resolved ? 'rgba(16, 185, 129, 0.04)' : 'rgba(245, 158, 11, 0.04)',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {conflict.resolved ? (
            <CheckCircle2 color="var(--color-success)" size={20} />
          ) : (
            <AlertTriangle color="var(--color-warning)" size={20} />
          )}
          <span 
            style={{ 
              fontWeight: 600, 
              color: conflict.resolved ? 'var(--color-success)' : 'var(--color-warning)',
              fontSize: '0.95rem'
            }}
          >
            {conflict.resolved ? 'Resolved Conflict' : 'Active Contradiction'}
          </span>
        </div>
        {conflict.resolved && conflict.resolution_meeting_id && (
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Resolved in <SourceBadge meetingId={conflict.resolution_meeting_id} />
          </span>
        )}
      </div>

      <div style={{ fontSize: '0.95rem', fontWeight: 500, lineHeight: 1.4 }}>
        {conflict.description}
      </div>

      <div 
        style={{ 
          display: 'grid', 
          gridTemplateColumns: '1fr 1fr', 
          gap: '1rem',
          padding: '0.75rem',
          borderRadius: 'var(--radius-sm)',
          backgroundColor: 'rgba(0, 0, 0, 0.2)',
          fontSize: '0.85rem'
        }}
      >
        <div>
          <div style={{ color: 'var(--text-muted)', marginBottom: '0.25rem', fontWeight: 600 }}>FACT A</div>
          <div style={{ color: 'var(--text-secondary)', fontStyle: 'italic', marginBottom: '0.5rem' }}>
            "{conflict.fact_a_text}"
          </div>
          <SourceBadge meetingId={conflict.meeting_a_id} />
        </div>
        <div>
          <div style={{ color: 'var(--text-muted)', marginBottom: '0.25rem', fontWeight: 600 }}>FACT B</div>
          <div style={{ color: 'var(--text-secondary)', fontStyle: 'italic', marginBottom: '0.5rem' }}>
            "{conflict.fact_b_text}"
          </div>
          <SourceBadge meetingId={conflict.meeting_b_id} />
        </div>
      </div>
    </div>
  );
};
