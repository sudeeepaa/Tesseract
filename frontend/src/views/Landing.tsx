import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles, ArrowRight, Play, Share2, Shield, Brain, Database, FileText,
  AlertTriangle, Users, Target, Layers, Lock, CheckCircle2, Cpu
} from 'lucide-react';

export const LandingView: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="page stack-lg" style={{ maxWidth: 1050, margin: '0 auto', paddingBottom: 60 }}>
      {/* ── HERO SECTION ──────────────────────────────────────────────────────── */}
      <section style={{
        textAlign: 'center',
        padding: '48px 24px',
        borderRadius: 'var(--r-lg)',
        background: 'linear-gradient(180deg, var(--accent-soft) 0%, var(--bg-sunken) 100%)',
        border: '1px solid var(--border-strong)',
        position: 'relative',
        overflow: 'hidden'
      }}>
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '6px 14px',
          borderRadius: 20,
          background: 'var(--surface)',
          border: '1px solid var(--border-strong)',
          fontSize: 12.5,
          fontWeight: 600,
          color: 'var(--accent)',
          marginBottom: 20
        }}>
          <Sparkles size={14} /> Multi-Agent Executive Chief of Staff
        </div>

        <h1 style={{
          fontSize: '2.5rem',
          fontWeight: 800,
          letterSpacing: '-0.03em',
          lineHeight: 1.15,
          maxWidth: 820,
          margin: '0 auto 16px',
          color: 'var(--text)'
        }}>
          Meetings pass. Decisions evolve.<br />
          <span style={{ color: 'var(--accent)' }}>Tesseract remembers everything.</span>
        </h1>

        <p className="page-lead" style={{ maxWidth: 720, margin: '0 auto 28px', fontSize: 16, lineHeight: 1.6 }}>
          Existing tools transcribe calls into dead text. Tesseract extracts structured decisions, tracks their lifecycle across sequential meetings, and flags logical contradictions before they stall execution.
        </p>

        <div className="row" style={{ justifyContent: 'center', gap: 12, flexWrap: 'wrap' }}>
          <button className="btn btn-primary" style={{ padding: '12px 24px', fontSize: 14.5 }} onClick={() => navigate('/add')}>
            <Play size={16} /> Try Demo Presets
          </button>
          <button className="btn btn-outline" style={{ padding: '12px 24px', fontSize: 14.5 }} onClick={() => navigate('/')}>
            <ArrowRight size={16} /> Open Command Center
          </button>
          <button className="btn btn-ghost" style={{ padding: '12px 24px', fontSize: 14.5 }} onClick={() => navigate('/map')}>
            <Share2 size={16} /> Explore Graph
          </button>
        </div>
      </section>

      {/* ── THE PROBLEM VS TESSERACT ───────────────────────────────────────────── */}
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
        <div className="card card-pad" style={{ background: 'var(--red-soft)', borderColor: 'rgba(207, 82, 69, 0.2)' }}>
          <div className="row" style={{ gap: 8, color: 'var(--red)', marginBottom: 12 }}>
            <AlertTriangle size={20} />
            <h3 style={{ fontSize: 16, fontWeight: 700 }}>The Traditional Meeting Trap</h3>
          </div>
          <ul className="stack" style={{ gap: 10, paddingLeft: 0, listStyle: 'none', fontSize: 13.5, color: 'var(--text-2)' }}>
            <li className="row" style={{ gap: 8, alignItems: 'flex-start' }}>
              <span style={{ color: 'var(--red)', fontWeight: 700 }}>✕</span>
              <span><strong>Isolated Transcripts:</strong> Meetings treat every call as an island, losing historical context.</span>
            </li>
            <li className="row" style={{ gap: 8, alignItems: 'flex-start' }}>
              <span style={{ color: 'var(--red)', fontWeight: 700 }}>✕</span>
              <span><strong>Silent Contradictions:</strong> Team A decides Auth0 in Week 1; Team B picks Firebase in Week 3. Nobody notices until build time.</span>
            </li>
            <li className="row" style={{ gap: 8, alignItems: 'flex-start' }}>
              <span style={{ color: 'var(--red)', fontWeight: 700 }}>✕</span>
              <span><strong>Lost Ownership:</strong> Action items get buried in meeting notes without a persistent tracking chain.</span>
            </li>
          </ul>
        </div>

        <div className="card card-pad" style={{ background: 'var(--green-soft)', borderColor: 'rgba(47, 146, 104, 0.2)' }}>
          <div className="row" style={{ gap: 8, color: 'var(--green)', marginBottom: 12 }}>
            <CheckCircle2 size={20} />
            <h3 style={{ fontSize: 16, fontWeight: 700 }}>The Tesseract Solution</h3>
          </div>
          <ul className="stack" style={{ gap: 10, paddingLeft: 0, listStyle: 'none', fontSize: 13.5, color: 'var(--text-2)' }}>
            <li className="row" style={{ gap: 8, alignItems: 'flex-start' }}>
              <span style={{ color: 'var(--green)', fontWeight: 700 }}>✓</span>
              <span><strong>Decision Lifecycles:</strong> Tracks status evolution: <code>proposed → confirmed → under_review → superseded</code>.</span>
            </li>
            <li className="row" style={{ gap: 8, alignItems: 'flex-start' }}>
              <span style={{ color: 'var(--green)', fontWeight: 700 }}>✓</span>
              <span><strong>Instant Conflict Detection:</strong> Cross-checks new claims against Neo4j knowledge graphs and Qdrant vectors.</span>
            </li>
            <li className="row" style={{ gap: 8, alignItems: 'flex-start' }}>
              <span style={{ color: 'var(--green)', fontWeight: 700 }}>✓</span>
              <span><strong>Human-in-the-Loop:</strong> Provides interactive "Keep", "Switch", or "Flag" resolution workflows.</span>
            </li>
          </ul>
        </div>
      </section>

      {/* ── TARGET AUDIENCE ───────────────────────────────────────────────────── */}
      <section className="card card-pad stack">
        <div>
          <div className="page-eyebrow">Who is Tesseract built for?</div>
          <h2 style={{ fontSize: 20, fontWeight: 700, marginTop: 4 }}>Target Audience &amp; Use Cases</h2>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, marginTop: 8 }}>
          <div style={{ padding: 16, borderRadius: 'var(--r-md)', background: 'var(--bg-sunken)', border: '1px solid var(--border)' }}>
            <Users size={20} color="var(--accent)" style={{ marginBottom: 8 }} />
            <div style={{ fontWeight: 650, fontSize: 14 }}>Executive Chiefs of Staff</div>
            <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>
              Get automated executive briefings, high-level decision summaries, and cross-team alignment updates without reading hours of transcripts.
            </div>
          </div>

          <div style={{ padding: 16, borderRadius: 'var(--r-md)', background: 'var(--bg-sunken)', border: '1px solid var(--border)' }}>
            <Target size={20} color="var(--accent)" style={{ marginBottom: 8 }} />
            <div style={{ fontWeight: 650, fontSize: 14 }}>Product &amp; Project Managers</div>
            <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>
              Maintain accountability for action items, prevent scope drift, and ensure technical decisions superseding old ones are explicitly tracked.
            </div>
          </div>

          <div style={{ padding: 16, borderRadius: 'var(--r-md)', background: 'var(--bg-sunken)', border: '1px solid var(--border)' }}>
            <Cpu size={20} color="var(--accent)" style={{ marginBottom: 8 }} />
            <div style={{ fontWeight: 650, fontSize: 14 }}>Engineering Leaders &amp; Architects</div>
            <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>
              Visualize architecture decisions and dependency chains using D3 relationship graphs and full Neo4j supersession traces.
            </div>
          </div>

          <div style={{ padding: 16, borderRadius: 'var(--r-md)', background: 'var(--bg-sunken)', border: '1px solid var(--border)' }}>
            <Lock size={20} color="var(--accent)" style={{ marginBottom: 8 }} />
            <div style={{ fontWeight: 650, fontSize: 14 }}>Compliance &amp; Governance Teams</div>
            <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>
              Enforce GDPR Article 17 data compliance with one-click cascading purges of speaker metadata across vector points and graph nodes.
            </div>
          </div>
        </div>
      </section>

      {/* ── CORE PILLARS ──────────────────────────────────────────────────────── */}
      <section className="stack-lg">
        <div style={{ textAlign: 'center' }}>
          <div className="page-eyebrow">Enterprise Architecture</div>
          <h2 style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>Core Technical Capabilities</h2>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
          <div className="card card-pad">
            <Brain size={22} color="var(--accent)" style={{ marginBottom: 10 }} />
            <h3 style={{ fontSize: 15, fontWeight: 650 }}>Multi-Agent Reasoning Pipeline</h3>
            <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>
              Orchestrates 6 specialized agents (Input, Extraction, Graph Writer, Semantic Memory, Briefing, Manager) using Lyzr Studio as primary and Google ADK as fallback.
            </p>
          </div>

          <div className="card card-pad">
            <Share2 size={22} color="var(--accent)" style={{ marginBottom: 10 }} />
            <h3 style={{ fontSize: 15, fontWeight: 650 }}>Neo4j Knowledge Graph</h3>
            <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>
              Stores entities, decisions, and action items as connected graph nodes. Tracks direct <code>SUPERSEDES</code> and <code>CONTRADICTS</code> relationships with audit trails.
            </p>
          </div>

          <div className="card card-pad">
            <Database size={22} color="var(--accent)" style={{ marginBottom: 10 }} />
            <h3 style={{ fontSize: 15, fontWeight: 650 }}>Qdrant Vector Memory</h3>
            <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>
              Vector-indexes all extracted claims and facts into a 384-dimensional space using <code>all-MiniLM-L6-v2</code> or <code>Gemini Embeddings</code> for instant natural-language search.
            </p>
          </div>

          <div className="card card-pad">
            <Shield size={22} color="var(--accent)" style={{ marginBottom: 10 }} />
            <h3 style={{ fontSize: 15, fontWeight: 650 }}>GDPR Article 17 Purging</h3>
            <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>
              Built-in governance engine scrubs speaker PII from Qdrant payloads and Neo4j speaker nodes without corrupting the surrounding decision memory.
            </p>
          </div>

          <div className="card card-pad">
            <Layers size={22} color="var(--accent)" style={{ marginBottom: 10 }} />
            <h3 style={{ fontSize: 15, fontWeight: 650 }}>Zero-Dependency Fallback</h3>
            <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>
              Auto-degrades to in-memory Graph/Vector stores and mock LLM extractors if third-party cloud APIs are unreachable, ensuring 100% demo availability.
            </p>
          </div>

          <div className="card card-pad">
            <FileText size={22} color="var(--accent)" style={{ marginBottom: 10 }} />
            <h3 style={{ fontSize: 15, fontWeight: 650 }}>Multimodal Input Support</h3>
            <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>
              Accepts plain text transcripts (.txt, .md) and raw audio recordings (.mp3, .wav, .m4a) transcribed via Gemini Flash native audio understanding or Whisper API.
            </p>
          </div>
        </div>
      </section>

      {/* ── CALL TO ACTION ────────────────────────────────────────────────────── */}
      <section className="card card-pad" style={{
        textAlign: 'center',
        padding: '36px 20px',
        background: 'var(--surface)',
        border: '1.5px solid var(--accent)',
        borderRadius: 'var(--r-lg)'
      }}>
        <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 8 }}>Ready to explore Tesseract?</h2>
        <p className="muted" style={{ fontSize: 14, maxWidth: 540, margin: '0 auto 20px' }}>
          Select from pre-loaded demo meetings or upload your own audio transcript to watch the multi-agent pipeline extract facts in real-time.
        </p>
        <div className="row" style={{ justifyContent: 'center', gap: 12 }}>
          <button className="btn btn-primary" onClick={() => navigate('/add')}>
            <Play size={15} /> Select Demo Meetings
          </button>
          <button className="btn btn-outline" onClick={() => navigate('/')}>
            Go to Command Center
          </button>
        </div>
      </section>
    </div>
  );
};
