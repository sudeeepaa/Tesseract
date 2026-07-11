import React from 'react';

interface StatusDotProps {
  status: 'connected' | 'degraded' | 'error';
  label: string;
  detail?: string;
}

export const StatusDot: React.FC<StatusDotProps> = ({ status, label, detail }) => {
  const getColors = () => {
    switch (status) {
      case 'connected':
        return { bg: '#10b981', shadow: 'rgba(16, 185, 129, 0.4)', text: 'Connected' };
      case 'degraded':
        return { bg: '#f59e0b', shadow: 'rgba(245, 158, 11, 0.4)', text: 'InMemory' };
      case 'error':
        return { bg: '#ef4444', shadow: 'rgba(239, 68, 68, 0.4)', text: 'Offline' };
    }
  };

  const colors = getColors();

  return (
    <div 
      className="glass-panel" 
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.5rem',
        padding: '0.4rem 0.75rem',
        borderRadius: 'var(--radius-sm)',
        fontSize: '0.85rem',
        backgroundColor: 'rgba(22, 28, 38, 0.4)',
        borderColor: 'var(--border-glass)',
        cursor: 'default'
      }}
      title={detail || `${label}: ${colors.text}`}
    >
      <span 
        style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          backgroundColor: colors.bg,
          boxShadow: `0 0 8px ${colors.shadow}`,
          display: 'inline-block'
        }}
        className={status === 'degraded' ? 'pulse-active' : ''}
      />
      <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>{label}:</span>
      <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{colors.text}</span>
    </div>
  );
};
