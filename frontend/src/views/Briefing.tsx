import React, { useState, useEffect } from 'react';
import { Loader2, FileText, CheckCircle2, AlertTriangle, HelpCircle, RefreshCw, Calendar, User } from 'lucide-react';
import { apiClient, BriefingOutput, Decision, ActionItem } from '../api/client';
import { SourceBadge } from '../components/SourceBadge';
import { ConflictAlert } from '../components/ConflictAlert';

export const BriefingView: React.FC = () => {
  const [briefing, setBriefing] = useState<BriefingOutput | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBriefing = async (showRefreshIndicator = false) => {
    try {
      if (showRefreshIndicator) setRefreshing(true);
      const data = await apiClient.getBriefing();
      setBriefing(data);
      setError(null);
    } catch (e) {
      console.error('Failed to load briefing:', e);
      setError('Could not retrieve compiled briefing data. Ensure the backend is online.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchBriefing();
    // Poll the server for updates every 15 seconds
    const interval = setInterval(() => fetchBriefing(true), 15000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '50vh', gap: '1rem' }}>
        <Loader2 className="pulse-active" size={40} color="var(--primary)" style={{ animation: 'spin 2s linear infinite' }} />
        <span style={{ color: 'var(--text-secondary)' }}>Compiling meeting summaries...</span>
        <style>{`@keyframes spin { 100% { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (error || !briefing) {
    return (
      <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center', maxWidth: '600px', margin: '4rem auto' }}>
        <AlertTriangle size={48} color="var(--color-error)" style={{ margin: '0 auto 1rem' }} />
        <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>Error Loading Briefing</h3>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>{error}</p>
        <button 
          onClick={() => fetchBriefing()} 
          style={{
            padding: '0.6rem 1.25rem',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: 'var(--primary)',
            color: '#fff',
            fontWeight: 600,
            cursor: 'pointer'
          }}
        >
          Try Again
        </button>
      </div>
    );
  }

  // Group decisions
  const activeDecisions = briefing.decisions.filter(d => d.status === 'confirmed');
  const underReviewDecisions = briefing.decisions.filter(d => d.status === 'under_review');
  const supersededDecisions = briefing.decisions.filter(d => d.status === 'superseded');
  const openActionItems = briefing.action_items.filter(a => a.status === 'open' || a.status === 'in_progress');
  const completedActionItems = briefing.action_items.filter(a => a.status === 'completed');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Header banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', marginBottom: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FileText color="var(--primary)" size={28} />
            Executive Briefing
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
            Fact summaries, action trackers, and conflict logs aggregated across {briefing.meeting_count} meeting(s).
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Last generated: {new Date(briefing.generated_at).toLocaleTimeString()}
          </span>
          <button 
            onClick={() => fetchBriefing(true)}
            style={{
              background: 'none',
              border: '1px solid var(--border-glass)',
              borderRadius: '50%',
              width: '36px',
              height: '36px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              color: 'var(--text-secondary)'
            }}
            title="Refresh briefing content"
          >
            <RefreshCw size={16} className={refreshing ? 'pulse-active' : ''} />
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.8fr 1.2fr', gap: '2rem' }}>
        
        {/* Left Side: Structured decisions & action items list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* Active Decisions */}
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1.25rem', color: '#fff', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <CheckCircle2 color="var(--color-success)" size={20} />
              Confirmed Decisions
            </h3>
            {activeDecisions.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>No active decisions confirmed yet.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {activeDecisions.map(d => (
                  <div 
                    key={d.id} 
                    style={{ 
                      padding: '1rem', 
                      borderRadius: 'var(--radius-sm)', 
                      backgroundColor: 'rgba(255, 255, 255, 0.02)',
                      border: '1px solid var(--border-glass)'
                    }}
                  >
                    <div style={{ display: 'flex', justifySelf: 'stretch', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
                      <span style={{ fontWeight: 600, fontSize: '0.95rem', color: 'var(--text-primary)' }}>{d.text}</span>
                      <SourceBadge meetingId={d.source_meeting_id} />
                    </div>
                    {d.rationale && (
                      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.5rem', borderLeft: '2px solid var(--primary)', paddingLeft: '0.5rem' }}>
                        {d.rationale}
                      </p>
                    )}
                    {d.owner && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
                        <User size={12} />
                        <span>Owner: {d.owner}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Under Review decisions (FLAGGED but not superseded) */}
          {underReviewDecisions.length > 0 && (
            <div className="glass-panel" style={{ padding: '1.5rem', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
              <h3 style={{ fontSize: '1.25rem', color: 'var(--color-warning)', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <AlertTriangle color="var(--color-warning)" size={20} />
                Decisions Under Review
              </h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
                These prior decisions have been flagged or put into question, but no replacement provider has been finalized yet.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {underReviewDecisions.map(d => (
                  <div 
                    key={d.id} 
                    style={{ 
                      padding: '1rem', 
                      borderRadius: 'var(--radius-sm)', 
                      backgroundColor: 'rgba(245, 158, 11, 0.03)',
                      border: '1px solid rgba(245, 158, 11, 0.15)'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
                      <span style={{ textDecoration: 'line-through', color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
                        {d.text}
                      </span>
                      <SourceBadge meetingId={d.source_meeting_id} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Action Items List */}
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1.25rem', color: '#fff', marginBottom: '1.25rem' }}>📋 Action Tracker</h3>
            
            {openActionItems.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>No open tasks currently assigned.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {openActionItems.map(a => (
                  <div 
                    key={a.id} 
                    style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'space-between',
                      padding: '0.75rem 1rem', 
                      borderRadius: 'var(--radius-sm)', 
                      backgroundColor: 'rgba(255, 255, 255, 0.01)',
                      border: '1px solid var(--border-glass)'
                    }}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      <span style={{ fontSize: '0.95rem', fontWeight: 500 }}>{a.text}</span>
                      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                        {a.assignee && (
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                            <User size={12} />
                            {a.assignee}
                          </span>
                        )}
                        {a.due_date && (
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                            <Calendar size={12} />
                            {a.due_date}
                          </span>
                        )}
                      </div>
                    </div>
                    <SourceBadge meetingId={a.source_meeting_id} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Side: Conflicts and historical decisions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {/* Conflicts alerts panel */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <h3 style={{ fontSize: '1.15rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Active Warnings</h3>
            {briefing.conflicts.length === 0 ? (
              <div className="glass-panel" style={{ padding: '1.25rem', color: 'var(--text-muted)', fontStyle: 'italic', fontSize: '0.9rem' }}>
                Zero active contradictions found. Factual consistency index: 100%
              </div>
            ) : (
              briefing.conflicts.map(c => <ConflictAlert key={c.id} conflict={c} />)
            )}
          </div>

          {/* Historical Superseded Decisions */}
          {supersededDecisions.length > 0 && (
            <div className="glass-panel" style={{ padding: '1.5rem', backgroundColor: 'rgba(0, 0, 0, 0.15)' }}>
              <h3 style={{ fontSize: '1.1rem', color: 'var(--text-muted)', marginBottom: '1rem', fontWeight: 600 }}>📜 Superseded decisions log</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {supersededDecisions.map(d => (
                  <div key={d.id} style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', fontSize: '0.85rem' }}>
                    <span style={{ textDecoration: 'line-through', color: 'var(--text-muted)', flex: 1 }}>{d.text}</span>
                    <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>[{d.source_meeting_id}]</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Topics bubble list */}
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <h3 style={{ fontSize: '1.1rem', color: 'var(--text-secondary)', marginBottom: '1rem', fontWeight: 600 }}>Key Topics discussed</h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              {briefing.topics.map(topic => (
                <span 
                  key={topic} 
                  style={{
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    color: 'var(--text-secondary)',
                    padding: '0.3rem 0.6rem',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.8rem',
                    border: '1px solid var(--border-glass)'
                  }}
                >
                  #{topic}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
