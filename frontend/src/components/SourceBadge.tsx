import React from 'react';
import { FileText } from 'lucide-react';

interface SourceBadgeProps {
  meetingId: string;
}

export const SourceBadge: React.FC<SourceBadgeProps> = ({ meetingId }) => {
  return (
    <span 
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.25rem',
        padding: '0.2rem 0.5rem',
        borderRadius: '4px',
        fontSize: '0.75rem',
        fontWeight: 600,
        backgroundColor: 'rgba(79, 70, 229, 0.12)',
        color: '#818cf8',
        border: '1px solid rgba(79, 70, 229, 0.3)',
        fontFamily: 'var(--font-mono)',
        cursor: 'default'
      }}
      title={`Source meeting: ${meetingId}`}
    >
      <FileText size={12} />
      {meetingId}
    </span>
  );
};
