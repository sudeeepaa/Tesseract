import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  CalendarDays, ClipboardCheck, ListTodo, Hash, Sparkles, Download,
  ChevronDown, Loader2, Plus,
} from 'lucide-react';
import { apiClient, MeetingSummary } from '../api/client';
import { EmptyState, SkeletonLines } from '../components/ui';
import { meetingLabel } from '../components/SourceBadge';

function fmtDate(iso?: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

/** Minimal markdown → JSX: headings, bold, and bullet lists. */
const MiniMarkdown: React.FC<{ text: string }> = ({ text }) => {
  const bold = (s: string) =>
    s.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
      part.startsWith('**') && part.endsWith('**')
        ? <strong key={i}>{part.slice(2, -2)}</strong>
        : <React.Fragment key={i}>{part}</React.Fragment>);

  const blocks: React.ReactNode[] = [];
  let bullets: string[] = [];
  const flush = () => {
    if (bullets.length) {
      blocks.push(
        <ul key={`ul-${blocks.length}`} style={{ margin: '4px 0 12px', paddingLeft: 20, lineHeight: 1.6 }}>
          {bullets.map((b, i) => <li key={i}>{bold(b)}</li>)}
        </ul>
      );
      bullets = [];
    }
  };

  text.split('\n').forEach((raw, i) => {
    const line = raw.trim();
    if (!line) { flush(); return; }
    if (/^#{1,6}\s/.test(line)) {
      flush();
      blocks.push(<h3 key={`h-${i}`} style={{ fontSize: 16, fontWeight: 650, margin: '8px 0 6px' }}>{line.replace(/^#{1,6}\s/, '')}</h3>);
    } else if (/^[-*]\s/.test(line)) {
      bullets.push(line.replace(/^[-*]\s/, ''));
    } else {
      flush();
      blocks.push(<p key={`p-${i}`} style={{ margin: '0 0 10px', lineHeight: 1.6 }}>{bold(line)}</p>);
    }
  });
  flush();
  return <div>{blocks}</div>;
};

const MeetingCard: React.FC<{ m: MeetingSummary }> = ({ m }) => {
  const [open, setOpen] = useState(false);
  // Summaries are generated once at ingestion, so they usually arrive with the
  // list — use that directly and only fetch as a fallback for older meetings.
  const [summary, setSummary] = useState<string | null>(m.summary ?? null);
  const [loading, setLoading] = useState(false);
  const date = fmtDate(m.recorded_at) || fmtDate(m.ingested_at);

  const loadSummary = useCallback(async () => {
    if (summary || loading) return;
    setLoading(true);
    try { setSummary((await apiClient.getMeetingSummary(m.id)).summary_markdown); }
    catch { setSummary('Could not load the summary right now. Please try again.'); }
    finally { setLoading(false); }
  }, [m.id, summary, loading]);

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next) loadSummary();
  }

  function download() {
    const body = summary || '';
    const blob = new Blob([`# ${m.title}\n\n${body}\n`], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${m.id}-summary.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="card card-pad">
      <div className="between" style={{ alignItems: 'flex-start', gap: 12 }}>
        <div className="grow">
          <div style={{ fontWeight: 650, fontSize: 16 }}>{meetingLabel(m.id)}</div>
          {m.title && m.title !== meetingLabel(m.id) && (
            <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>{m.title}</div>
          )}
          <div className="row wrap" style={{ gap: 14, marginTop: 10, fontSize: 12.5, color: 'var(--text-muted)' }}>
            {date && <span className="row" style={{ gap: 5 }}><CalendarDays size={13} /> {date}</span>}
            <span className="row" style={{ gap: 5 }}><ClipboardCheck size={13} /> {m.decision_count} decision{m.decision_count === 1 ? '' : 's'}</span>
            <span className="row" style={{ gap: 5 }}><ListTodo size={13} /> {m.action_item_count} task{m.action_item_count === 1 ? '' : 's'}</span>
            {m.topic_count > 0 && <span className="row" style={{ gap: 5 }}><Hash size={13} /> {m.topic_count} topic{m.topic_count === 1 ? '' : 's'}</span>}
          </div>
          {m.preview && !open && (
            <div className="muted" style={{ fontSize: 13, marginTop: 10, lineHeight: 1.5 }}>{m.preview}…</div>
          )}
        </div>
        <button className="btn btn-outline btn-sm" onClick={toggle} style={{ flex: 'none' }}>
          <Sparkles size={14} /> Summary
          <ChevronDown size={14} style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .15s' }} />
        </button>
      </div>

      {open && (
        <div style={{ marginTop: 14, borderTop: '1px solid var(--border)', paddingTop: 14 }}>
          {loading && <div className="row muted" style={{ gap: 8, fontSize: 13.5 }}><Loader2 size={15} className="spin" /> Writing the summary…</div>}
          {!loading && summary && (
            <>
              <div style={{ fontSize: 14.5 }}><MiniMarkdown text={summary} /></div>
              <div className="row" style={{ marginTop: 12 }}>
                <button className="btn btn-outline btn-sm" onClick={download}><Download size={14} /> Download .md</button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export const MeetingsView: React.FC = () => {
  const [meetings, setMeetings] = useState<MeetingSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try { setMeetings((await apiClient.listMeetings()).meetings); }
    catch { /* leave empty */ } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="page stack-lg">
      <header>
        <div className="page-eyebrow">Meetings</div>
        <h1 className="page-title">Every meeting, at a glance</h1>
        <p className="page-lead">Each meeting Tesseract has processed — with a one-click AI summary you can read or download.</p>
      </header>

      {loading && <SkeletonLines rows={4} />}

      {!loading && meetings.length === 0 && (
        <EmptyState icon={<CalendarDays size={22} />} title="No meetings yet"
          children={<>Add your first meeting and it'll show up here with a summary.</>}
          action={<Link to="/add" className="btn btn-primary btn-sm"><Plus size={15} /> Add a meeting</Link>} />
      )}

      {!loading && meetings.length > 0 && (
        <div className="stack-sm">
          {meetings.map((m) => <MeetingCard key={m.id} m={m} />)}
        </div>
      )}
    </div>
  );
};
