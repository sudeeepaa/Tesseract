import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { Upload, FileText, Share2, Search, Database, RefreshCw } from 'lucide-react';
import { apiClient, BackendStatus } from './api/client';
import { StatusDot } from './components/StatusDot';

// Views
import { UploadView } from './views/Upload';
import { BriefingView } from './views/Briefing';
import { GraphView } from './views/Graph';
import { SearchView } from './views/Search';

export const App: React.FC = () => {
  const [status, setStatus] = useState<BackendStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  const fetchStatus = async () => {
    try {
      setRefreshing(true);
      const data = await apiClient.getStatus();
      setStatus(data);
    } catch (e) {
      console.error('Failed to retrieve system status:', e);
      // Fallback state on fetch error
      setStatus({
        neo4j: { connected: false, node_count: 0, edge_count: 0, backend: 'neo4j', error: 'Unreachable' },
        qdrant: { connected: false, vector_count: 0, backend: 'qdrant', error: 'Unreachable' },
        llm: { backend: 'mock' }
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    // Refresh status automatically every 20 seconds
    const interval = setInterval(fetchStatus, 20000);
    return () => clearInterval(interval);
  }, []);

  return (
    <BrowserRouter>
      <div className="app-container">
        {/* Navigation bar with status dots */}
        <header className="app-navbar">
          <div className="brand-section">
            <Database size={24} color="#4f46e5" />
            <h1 className="brand-title">Threadline</h1>
          </div>

          <nav className="nav-links">
            <NavLink to="/" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} end>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Upload size={16} />
                <span>Upload</span>
              </div>
            </NavLink>
            <NavLink to="/briefing" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <FileText size={16} />
                <span>Briefing</span>
              </div>
            </NavLink>
            <NavLink to="/graph" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Share2 size={16} />
                <span>Graph Viz</span>
              </div>
            </NavLink>
            <NavLink to="/search" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Search size={16} />
                <span>Semantic Search</span>
              </div>
            </NavLink>
          </nav>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {status && (
              <>
                <StatusDot 
                  status={status.neo4j.connected ? (status.neo4j.backend === 'memory' ? 'degraded' : 'connected') : 'error'} 
                  label="Neo4j" 
                  detail={status.neo4j.error || `${status.neo4j.node_count} nodes, ${status.neo4j.edge_count} edges`} 
                />
                <StatusDot 
                  status={status.qdrant.connected ? (status.qdrant.backend === 'memory' ? 'degraded' : 'connected') : 'error'} 
                  label="Qdrant" 
                  detail={status.qdrant.error || `${status.qdrant.vector_count} vectors`} 
                />
                <div 
                  className="glass-panel"
                  style={{
                    padding: '0.4rem 0.75rem',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.85rem',
                    backgroundColor: 'rgba(22, 28, 38, 0.4)',
                    borderColor: 'var(--border-glass)',
                    cursor: 'default',
                    color: 'var(--text-secondary)'
                  }}
                  title={`LLM Extraction Backend: ${status.llm.backend}`}
                >
                  LLM: <span style={{ fontWeight: 600, color: 'var(--text-primary)', textTransform: 'capitalize' }}>{status.llm.backend}</span>
                </div>
              </>
            )}
            <button 
              onClick={fetchStatus} 
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--text-secondary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '0.5rem',
                borderRadius: '50%',
                transition: 'var(--transition-smooth)'
              }}
              title="Refresh connectivity status"
              className={refreshing ? 'pulse-active' : ''}
            >
              <RefreshCw size={16} style={{ transform: refreshing ? 'rotate(180deg)' : 'none', transition: 'transform 0.5s ease' }} />
            </button>
          </div>
        </header>

        {/* Router views placement */}
        <main className="main-content">
          <Routes>
            <Route path="/" element={<UploadView onPipelineSuccess={fetchStatus} />} />
            <Route path="/briefing" element={<BriefingView />} />
            <Route path="/graph" element={<GraphView />} />
            <Route path="/search" element={<SearchView />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
};

export default App;
