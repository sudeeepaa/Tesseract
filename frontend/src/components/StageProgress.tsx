import React from 'react';
import { Loader2, CheckCircle2, XCircle, ChevronRight, HelpCircle } from 'lucide-react';
import { PipelineStageEvent } from '../api/client';

interface StageProgressProps {
  events: PipelineStageEvent[];
}

export const StageProgress: React.FC<StageProgressProps> = ({ events }) => {
  // Order of stages to display
  const stages: Array<'INGEST' | 'TRANSCRIBE' | 'EXTRACT' | 'GRAPH_WRITE' | 'VECTOR_WRITE' | 'BRIEFING'> = [
    'INGEST',
    'TRANSCRIBE',
    'EXTRACT',
    'GRAPH_WRITE',
    'VECTOR_WRITE',
    'BRIEFING'
  ];

  const getStageLabel = (stage: string) => {
    switch (stage) {
      case 'INGEST': return 'Ingesting File';
      case 'TRANSCRIBE': return 'Transcribing';
      case 'EXTRACT': return 'Extracting Facts';
      case 'GRAPH_WRITE': return 'Writing Knowledge Graph';
      case 'VECTOR_WRITE': return 'Storing Vector Embeddings';
      case 'BRIEFING': return 'Compiling Briefing';
      default: return stage;
    }
  };

  const getStageStatus = (stage: string) => {
    // Find the latest status event for this stage
    const match = [...events].reverse().find(e => e.stage === stage);
    return match ? match.status : 'pending';
  };

  const getStageMessage = (stage: string) => {
    const match = [...events].reverse().find(e => e.stage === stage);
    return match ? match.message : '';
  };

  const renderIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <Loader2 className="pulse-active" size={20} color="var(--secondary)" style={{ animation: 'spin 2s linear infinite' }} />;
      case 'done':
        return <CheckCircle2 size={20} color="var(--color-success)" />;
      case 'error':
        return <XCircle size={20} color="var(--color-error)" />;
      case 'skipped':
        return <CheckCircle2 size={20} color="var(--color-dim)" style={{ opacity: 0.6 }} />;
      case 'pending':
      default:
        return <span style={{ width: '20px', height: '20px', borderRadius: '50%', border: '2px solid var(--border-glass)', display: 'inline-block' }} />;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', width: '100%' }}>
      {stages.map((stage, idx) => {
        const status = getStageStatus(stage);
        const msg = getStageMessage(stage);
        const isLast = idx === stages.length - 1;

        return (
          <div key={stage} style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <div 
              className="glass-panel" 
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '1rem',
                padding: '1rem 1.25rem',
                borderRadius: 'var(--radius-md)',
                backgroundColor: status === 'running' ? 'rgba(6, 182, 212, 0.05)' : 'var(--bg-card)',
                borderColor: status === 'running' ? 'var(--secondary)' : 'var(--border-glass)',
                opacity: status === 'pending' ? 0.5 : 1,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {renderIcon(status)}
              </div>
              
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 600, fontSize: '1rem', color: status === 'running' ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                    {getStageLabel(stage)}
                  </span>
                  <span 
                    style={{ 
                      fontSize: '0.75rem', 
                      textTransform: 'uppercase', 
                      fontWeight: 700,
                      color: status === 'running' ? 'var(--secondary)' : (status === 'done' ? 'var(--color-success)' : 'var(--text-muted)')
                    }}
                  >
                    {status}
                  </span>
                </div>
                {msg && (
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', marginTop: '0.25rem', fontFamily: 'var(--font-mono)' }}>
                    {msg}
                  </div>
                )}
              </div>
            </div>
            
            {!isLast && (
              <div 
                style={{ 
                  width: '2px', 
                  height: '16px', 
                  backgroundColor: 'var(--border-glass)', 
                  marginLeft: '22px',
                  opacity: status === 'done' ? 1 : 0.4
                }} 
              />
            )}
          </div>
        );
      })}
      
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};
