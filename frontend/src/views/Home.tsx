import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ClipboardCheck, ListTodo, CalendarDays, ShieldAlert, CheckCircle2,
  Sparkles, WifiOff, Loader2, ArrowRight,
} from 'lucide-react';
import { apiClient, BriefingOutput } from '../api/client';
import { useAppData, useToast } from '../state/app';
import { ConflictCard } from '../components/ConflictCard';
import { StatCard, EmptyState, SkeletonLines, StatusPill } from '../components/ui';
import { SourceBadge } from '../components/SourceBadge';

function greeting(): string {
  const h = new Date().getHours();
  const name = localStorage.getItem('tesseract-user');
  const part = h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
  return name && name !== 'You' ? `${part}, ${name}` : part;
}
const today = () =>
  new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });

export const HomeView: React.FC = () => {
  const { conflicts, unresolvedCount, online } = useAppData();
  const { notify } = useToast();
  const [briefing, setBriefing] = useState<BriefingOutput | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);

  const load = useCallback(async () => {
    try { setBriefing(await apiClient.getBriefing()); }
    catch { /* offline handled by context */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  async function seed() {
    setSeeding(true);
    try {
      const r = await apiClient.seedSampleMeetings();
      notify(`Loaded ${r.meetings_loaded} sample meetings.`, 'success');
      await load();
    } catch (e: any) {
      notify(e.message || 'Could not load samples.', 'error');
    } finally {
      setSeeding(false);
    }
  }

  const activeDecisions = briefing?.decisions.filter((d) => d.status === 'confirmed') ?? [];
  const openTasks = briefing?.action_items.filter((a) => a.status === 'open' || a.status === 'in_progress') ?? [];
  const open = conflicts.filter((c) => !c.resolved);
  const isEmpty = briefing && briefing.meeting_count === 0;

  return (
    <div className="page stack-lg">
      <header>
        <div className="page-eyebrow">Command Center · {today()}</div>
        <h1 className="page-title" style={{ fontFamily: 'var(--font-serif)', fontSize: 30, fontWeight: 600 }}>
          {greeting()}
        </h1>
        <p className="page-lead">Your meeting decisions, tasks, and anything that needs you — in one place.</p>
      </header>

      {loading && <SkeletonLines rows={4} />}

      {!loading && !briefing && !online && (
        <EmptyState icon={<WifiOff size={22} />} title="Can't reach your assistant"
          children={<>The assistant service isn’t responding. Make sure the backend is running, then try again.</>}
          action={<button className="btn btn-outline btn-sm" onClick={load}>Try again</button>} />
      )}

      {!loading && isEmpty && (
        <EmptyState icon={<Sparkles size={22} />} title="No meetings yet"
          children={<>Add your first meeting transcript, or load a few sample meetings to see how Tesseract tracks decisions and catches conflicts.</>}
          action={
            <div className="row" style={{ justifyContent: 'center' }}>
              <button className="btn btn-primary btn-sm" onClick={seed} disabled={seeding}>
                {seeding ? <Loader2 size={15} className="spin" /> : <Sparkles size={15} />} Load sample meetings
              </button>
              <Link to="/add" className="btn btn-outline btn-sm">Add a meeting</Link>
            </div>
          } />
      )}

      {!loading && briefing && !isEmpty && (
        <>
          {/* Signature: what needs a human decision */}
          <section>
            <div className="section-title">Needs your decision</div>
            {open.length > 0 ? (
              <div className="stack">
                {open.map((c) => (
                  <ConflictCard key={c.id} conflict={c} decisions={briefing.decisions} onResolved={load} />
                ))}
              </div>
            ) : (
              <div className="card card-pad row" style={{ gap: 12 }}>
                <CheckCircle2 size={20} color="var(--green)" />
                <div>
                  <div style={{ fontWeight: 600 }}>You’re all caught up</div>
                  <div className="muted" style={{ fontSize: 13.5 }}>No clashing decisions right now. We’ll raise a flag here the moment one appears.</div>
                </div>
              </div>
            )}
          </section>

          {/* At a glance */}
          <section className="stat-grid">
            <StatCard value={activeDecisions.length} label="Active decisions" icon={<ClipboardCheck size={14} />} />
            <StatCard value={openTasks.length} label="Open action items" icon={<ListTodo size={14} />} />
            <StatCard value={briefing.meeting_count} label="Meetings captured" icon={<CalendarDays size={14} />} />
            <StatCard value={unresolvedCount} label="Flagged for you"
              icon={<ShieldAlert size={14} />} accent={unresolvedCount > 0 ? 'var(--amber)' : undefined} />
          </section>

          {/* Latest decisions */}
          <section>
            <div className="between" style={{ marginBottom: 10 }}>
              <div className="section-title" style={{ margin: 0 }}>Latest decisions</div>
              <Link to="/decisions" className="btn btn-ghost btn-sm">View all <ArrowRight size={14} /></Link>
            </div>
            {activeDecisions.length === 0 ? (
              <div className="card card-pad muted" style={{ fontSize: 14 }}>No confirmed decisions yet.</div>
            ) : (
              <div className="card">
                {activeDecisions.slice(0, 4).map((d, i) => (
                  <div key={d.id} className="between" style={{
                    padding: '13px 16px', borderTop: i ? '1px solid var(--border)' : 'none', gap: 12,
                  }}>
                    <div className="grow">
                      <div style={{ fontWeight: 550, fontSize: 14.5 }}>{d.text}</div>
                      {d.owner && <div className="muted" style={{ fontSize: 12.5, marginTop: 2 }}>Owner: {d.owner}</div>}
                    </div>
                    <div className="row" style={{ gap: 8 }}>
                      <StatusPill value={d.status} />
                      <SourceBadge meetingId={d.source_meeting_id} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
};
