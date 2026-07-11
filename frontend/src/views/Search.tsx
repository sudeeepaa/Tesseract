import React, { useState } from 'react';
import { Search, Loader2, Sparkles, Award, User, Clock, ArrowRight } from 'lucide-react';
import { apiClient, SearchResult } from '../api/client';
import { SourceBadge } from '../components/SourceBadge';

export const SearchView: React.FC = () => {
  const [query, setQuery] = useState<string>('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [searched, setSearched] = useState<boolean>(false);

  const suggestedQueries = [
    'GDPR compliance and EU region',
    'Switching database choice from Postgres to MongoDB',
    'GDPR issues with Auth0 enterprise plan',
    'Keycloak authentication deployment date',
    'Wireframe deliverables timeline'
  ];

  const handleSearch = async (searchQuery: string) => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const resp = await apiClient.search(searchQuery);
      setResults(resp.results);
    } catch (e) {
      console.error('Failed to run semantic query:', e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem', maxWidth: '1000px', margin: '0 auto' }}>
      {/* Title */}
      <div>
        <h2 style={{ fontSize: '1.75rem', marginBottom: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Search color="var(--secondary)" size={28} />
          Concept-Level Semantic Search
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
          Query meeting facts semantically. Qdrant vector spaces find contextually similar sentences even if exact keywords don't match.
        </p>
      </div>

      {/* Input panel */}
      <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <form 
          onSubmit={(e) => { e.preventDefault(); handleSearch(query); }}
          style={{ display: 'flex', gap: '1rem' }}
        >
          <div style={{ position: 'relative', flex: 1 }}>
            <Search 
              size={20} 
              color="var(--text-muted)" 
              style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)' }} 
            />
            <input 
              type="text"
              placeholder="Search across all analyzed meeting claims..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '0.85rem 1rem 0.85rem 3rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-glass)',
                backgroundColor: 'rgba(0, 0, 0, 0.4)',
                color: 'var(--text-primary)',
                outline: 'none',
                fontSize: '1rem',
                transition: 'var(--transition-smooth)'
              }}
            />
          </div>
          <button 
            type="submit"
            disabled={loading}
            style={{
              padding: '0 1.5rem',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              backgroundColor: 'var(--primary)',
              color: '#fff',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              boxShadow: '0 4px 15px var(--primary-glow)'
            }}
          >
            {loading ? <Loader2 size={18} style={{ animation: 'spin 2s linear infinite' }} /> : 'Search'}
          </button>
        </form>

        {/* Suggestion list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <Sparkles size={12} color="var(--secondary)" />
            TRY SUGGESTED DEMO QUERIES:
          </span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {suggestedQueries.map(q => (
              <button 
                key={q}
                type="button"
                onClick={() => { setQuery(q); handleSearch(q); }}
                style={{
                  background: 'none',
                  border: '1px solid var(--border-glass)',
                  backgroundColor: 'rgba(255, 255, 255, 0.02)',
                  color: 'var(--text-secondary)',
                  padding: '0.35rem 0.75rem',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                  transition: 'var(--transition-smooth)',
                  textAlign: 'left'
                }}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Results panel */}
      {searched && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <h3 style={{ fontSize: '1.25rem', color: 'var(--text-secondary)' }}>
            Search Results ({results.length})
          </h3>
          
          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
              <Loader2 className="pulse-active" size={32} color="var(--primary)" style={{ animation: 'spin 2s linear infinite' }} />
            </div>
          ) : results.length === 0 ? (
            <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
              No matches found for your query. Try searching with other conceptual terms.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {results.map((res, index) => (
                <div 
                  key={res.fact_id + '-' + index} 
                  className="glass-panel" 
                  style={{ 
                    padding: '1.25rem', 
                    display: 'flex', 
                    flexDirection: 'column', 
                    gap: '0.75rem',
                    backgroundColor: 'rgba(22, 28, 38, 0.5)'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span 
                        style={{
                          backgroundColor: res.fact_type === 'decision' ? 'rgba(16, 185, 129, 0.12)' : 'rgba(249, 115, 22, 0.12)',
                          color: res.fact_type === 'decision' ? 'var(--color-success)' : '#fb923c',
                          padding: '0.2rem 0.5rem',
                          borderRadius: '4px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          textTransform: 'uppercase'
                        }}
                      >
                        {res.fact_type}
                      </span>
                      {res.speaker && (
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                          <User size={12} />
                          {res.speaker}
                        </span>
                      )}
                    </div>
                    
                    {/* Score badge bar indicator */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>
                        Match: {(res.score * 100).toFixed(0)}%
                      </span>
                      <div 
                        style={{ 
                          width: '60px', 
                          height: '6px', 
                          backgroundColor: 'rgba(255, 255, 255, 0.1)', 
                          borderRadius: '3px',
                          overflow: 'hidden'
                        }}
                      >
                        <div 
                          style={{ 
                            width: `${res.score * 100}%`, 
                            height: '100%', 
                            backgroundColor: 'var(--secondary)' 
                          }} 
                        />
                      </div>
                    </div>
                  </div>

                  <p style={{ fontSize: '1rem', fontWeight: 500, lineHeight: 1.4 }}>
                    {res.text}
                  </p>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-glass)', paddingTop: '0.5rem', marginTop: '0.25rem' }}>
                    <SourceBadge meetingId={res.meeting_id} />
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      ID: {res.fact_id}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      
      <style>{`@keyframes spin { 100% { transform: rotate(360deg); } }`}</style>
    </div>
  );
};
