import React, { useState } from 'react';
import { Search, Loader2, CornerDownLeft } from 'lucide-react';
import { apiClient, SearchResult } from '../api/client';
import { SourceBadge } from '../components/SourceBadge';
import { EmptyState } from '../components/ui';

const SUGGESTIONS = [
  'What did we decide about authentication?',
  'Why did we move off PostgreSQL?',
  'Anything about GDPR or EU data?',
  'What are the deadlines?',
];

export const AskView: React.FC = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  async function run(q: string) {
    if (!q.trim()) return;
    setLoading(true); setSearched(true); setQuery(q);
    try { setResults((await apiClient.search(q)).results); }
    catch { setResults([]); }
    finally { setLoading(false); }
  }

  return (
    <div className="page stack-lg">
      <header>
        <div className="page-eyebrow">Ask</div>
        <h1 className="page-title">Ask your meetings anything</h1>
        <p className="page-lead">Search by meaning, not just keywords — Tesseract finds the moments that match your question.</p>
      </header>

      <form onSubmit={(e) => { e.preventDefault(); run(query); }}>
        <div className="row" style={{ position: 'relative' }}>
          <Search size={18} color="var(--text-muted)" style={{ position: 'absolute', left: 12 }} />
          <input className="input" style={{ paddingLeft: 38, height: 44, fontSize: 15 }}
            placeholder="e.g. What did we decide about the database?"
            value={query} onChange={(e) => setQuery(e.target.value)} autoFocus />
          <button className="btn btn-primary" type="submit" disabled={loading} style={{ marginLeft: 8, height: 44 }}>
            {loading ? <Loader2 size={16} className="spin" /> : <>Ask <CornerDownLeft size={15} /></>}
          </button>
        </div>
      </form>

      {!searched && (
        <div className="col" style={{ gap: 8 }}>
          <div className="muted" style={{ fontSize: 13 }}>Try asking</div>
          <div className="row wrap" style={{ gap: 8 }}>
            {SUGGESTIONS.map((s) => (
              <button key={s} className="btn btn-outline btn-sm" onClick={() => run(s)}>{s}</button>
            ))}
          </div>
        </div>
      )}

      {searched && !loading && results.length === 0 && (
        <EmptyState icon={<Search size={22} />} title="Nothing matched"
          children={<>Try rephrasing, or ask about a different topic from your meetings.</>} />
      )}

      {searched && results.length > 0 && (
        <div className="stack-sm">
          {results.map((r, i) => {
            const pct = Math.round(r.score * 100);
            return (
              <div key={r.fact_id + i} className="card card-pad card-hover">
                <div className="between" style={{ marginBottom: 8 }}>
                  <span className={`pill pill-${r.fact_type === 'decision' ? 'green' : r.fact_type === 'action_item' ? 'amber' : 'gray'}`}>
                    {r.fact_type.replace('_', ' ')}
                  </span>
                  <span className="row muted" style={{ gap: 8, fontSize: 12.5 }}>
                    {pct}% match
                    <span className="match-bar"><span className="match-fill" style={{ width: `${pct}%` }} /></span>
                  </span>
                </div>
                <div style={{ fontSize: 15, fontWeight: 500, lineHeight: 1.45 }}>{r.text}</div>
                <div className="row" style={{ marginTop: 10 }}>
                  <SourceBadge meetingId={r.meeting_id} />
                  {r.speaker && <span className="muted" style={{ fontSize: 12.5, marginLeft: 8 }}>{r.speaker}</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
