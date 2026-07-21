import React, { useState } from 'react';
import { UserX, Sun, Moon, Trash2 } from 'lucide-react';
import { apiClient } from '../api/client';
import { useAppData, useTheme, useToast } from '../state/app';
import { ConfirmDialog } from '../components/ui';

const Field: React.FC<{ label: string; value: string; tone?: string }> = ({ label, value, tone }) => (
  <div className="between" style={{ padding: '10px 0', borderTop: '1px solid var(--border)' }}>
    <span className="muted" style={{ fontSize: 13.5 }}>{label}</span>
    <span style={{ fontSize: 13.5, fontWeight: 550, color: tone }}>{value}</span>
  </div>
);

export const SettingsView: React.FC = () => {
  const { status, online } = useAppData();
  const { theme, toggle } = useTheme();
  const { notify } = useToast();

  const [name, setName] = useState(localStorage.getItem('tesseract-user') || '');
  const [person, setPerson] = useState('');
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);

  function saveName() {
    localStorage.setItem('tesseract-user', name.trim());
    notify('Saved your name.', 'success');
  }

  async function purge() {
    setBusy(true);
    try {
      const r = await apiClient.purgePerson(person.trim());
      const g = r.purged_records?.graph_store || {};
      notify(`Removed ${person}. Cleared ${g.updated_decisions ?? 0} decision owner(s) and ${g.updated_action_items ?? 0} task(s).`, 'success');
      setPerson(''); setConfirm(false);
    } catch (e: any) {
      notify(e.message || 'Could not remove that person.', 'error');
    } finally { setBusy(false); }
  }

  const memoryMode = status && (status.neo4j.backend === 'memory' || status.qdrant.backend === 'memory');

  return (
    <div className="page stack-lg" style={{ maxWidth: 720 }}>
      <header>
        <div className="page-eyebrow">Settings &amp; privacy</div>
        <h1 className="page-title">Settings</h1>
      </header>

      <section className="card card-pad stack-sm">
        <h3 style={{ fontSize: 15 }}>Your name</h3>
        <p className="muted" style={{ fontSize: 13 }}>Used to greet you and to note who resolved a conflict.</p>
        <div className="row">
          <input className="input" placeholder="e.g. Sam" value={name} onChange={(e) => setName(e.target.value)} />
          <button className="btn btn-outline btn-sm" onClick={saveName} style={{ flex: 'none' }}>Save</button>
        </div>
      </section>

      <section className="card card-pad stack-sm">
        <div className="between">
          <div>
            <h3 style={{ fontSize: 15 }}>Appearance</h3>
            <p className="muted" style={{ fontSize: 13 }}>Currently {theme} mode.</p>
          </div>
          <button className="btn btn-outline btn-sm" onClick={toggle}>
            {theme === 'dark' ? <><Sun size={15} /> Light</> : <><Moon size={15} /> Dark</>}
          </button>
        </div>
      </section>

      <section className="card card-pad">
        <h3 style={{ fontSize: 15, marginBottom: 4 }}>System status</h3>
        <p className="muted" style={{ fontSize: 13 }}>For the technically curious. Everything degrades gracefully to a local demo mode.</p>
        <div style={{ marginTop: 10 }}>
          <Field label="Assistant" value={online ? 'Online' : 'Offline'} tone={online ? 'var(--green)' : 'var(--red)'} />
          <Field label="Memory (knowledge graph)" value={status?.neo4j.backend === 'neo4j' ? 'Neo4j (persistent)' : 'In-memory (demo)'} />
          <Field label="Search (vectors)" value={status?.qdrant.backend === 'qdrant' ? 'Qdrant (persistent)' : 'In-memory (demo)'} />
          <Field label="AI extraction" value={status?.llm.backend === 'mock' ? 'Demo (sample data)' : (status?.llm.backend || '—')} />
        </div>
        {memoryMode && (
          <p className="muted" style={{ fontSize: 12.5, marginTop: 10 }}>
            Running in local demo mode — data lives in memory for this session. Powered by Qdrant + Lyzr.
          </p>
        )}
      </section>

      <section className="card card-pad stack-sm">
        <h3 className="row" style={{ fontSize: 15, gap: 7 }}><UserX size={16} /> Remove a person (GDPR)</h3>
        <p className="muted" style={{ fontSize: 13 }}>
          Erase someone’s personal data — their name is removed from ownership and mentions everywhere. Decisions themselves are kept, just no longer attributed. This can’t be undone.
        </p>
        <div className="row">
          <input className="input" placeholder="Full name, e.g. Dev Rao" value={person} onChange={(e) => setPerson(e.target.value)} />
          <button className="btn btn-danger btn-sm" style={{ flex: 'none' }} disabled={!person.trim()} onClick={() => setConfirm(true)}>
            <Trash2 size={15} /> Remove
          </button>
        </div>
      </section>

      <ConfirmDialog open={confirm} danger busy={busy} confirmLabel="Remove permanently"
        title={`Remove ${person}?`}
        message={<>This erases <strong>{person}</strong>’s personal data across all meetings. Decisions stay, but will no longer show them as owner. This can’t be undone.</>}
        onConfirm={purge} onCancel={() => setConfirm(false)} />
    </div>
  );
};
