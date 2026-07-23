import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud, FileText, AudioLines, Play, Sparkles, CheckCircle2,
  AlertCircle, Loader2, FolderOpen, ArrowRight, Zap
} from 'lucide-react';
import { apiClient, PipelineStageEvent } from '../api/client';
import { StageProgress } from '../components/StageProgress';
import { useAppData, useToast } from '../state/app';
import { DEMO_PRESETS, DemoPreset } from '../data/demoPresets';

const AUDIO_EXT = ['mp3', 'wav', 'm4a', 'mp4', 'ogg', 'webm'];

export const AddMeetingView: React.FC = () => {
  const navigate = useNavigate();
  const { notify } = useToast();
  const { refreshConflicts, refreshStatus } = useAppData();

  const [file, setFile] = useState<File | null>(null);
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);
  const [meetingId, setMeetingId] = useState('');
  const [kind, setKind] = useState<'transcript' | 'audio'>('transcript');
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<PipelineStageEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const cancelRef = React.useRef<(() => void) | null>(null);

  const onDrop = useCallback((accepted: File[]) => {
    const f = accepted[0];
    if (!f) return;
    setFile(f);
    setSelectedPresetId(null);
    const stem = f.name.replace(/\.[^.]+$/, '');
    setMeetingId(stem.toLowerCase().replace(/[^a-z0-9_-]/g, '_'));
    const ext = f.name.split('.').pop()?.toLowerCase();
    setKind(ext && AUDIO_EXT.includes(ext) ? 'audio' : 'transcript');
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, maxFiles: 1,
    accept: kind === 'transcript'
      ? { 'text/plain': ['.txt'], 'text/markdown': ['.md'] }
      : { 'audio/*': AUDIO_EXT.map((e) => '.' + e) },
  });

  const selectPreset = (preset: DemoPreset) => {
    setSelectedPresetId(preset.id);
    setKind(preset.kind);
    setMeetingId(preset.id);

    if (preset.kind === 'audio') {
      // Audio preset representation
      const dummyAudio = new File(['[Audio File Bytes]'], preset.filename, { type: 'audio/mp3' });
      setFile(dummyAudio);
    } else {
      const textFile = new File([preset.content || ''], preset.filename, { type: 'text/plain' });
      setFile(textFile);
    }
  };

  function start() {
    if (!file) return;
    setRunning(true); setDone(false); setError(null); setEvents([]);
    const stream = apiClient.runPipelineStream(
      file, meetingId || undefined,
      (ev) => {
        setEvents((prev) => {
          const i = prev.findIndex((e) => e.stage === ev.stage);
          if (i >= 0) { const u = [...prev]; u[i] = ev; return u; }
          return [...prev, ev];
        });
        if (ev.stage === 'PIPELINE') {
          if (ev.status === 'done') {
            setDone(true); setRunning(false);
            notify('Meeting processed — your briefing is updated.', 'success');
            refreshConflicts(); refreshStatus();
          } else if (ev.status === 'error') {
            setError(ev.message); setRunning(false);
          }
        }
      },
      (err) => { setError(err.message || 'Something went wrong while processing.'); setRunning(false); }
    );
    cancelRef.current = stream.cancel;
  }

  async function seed() {
    setSeeding(true);
    try {
      const r = await apiClient.seedSampleMeetings();
      notify(`Loaded ${r.meetings_loaded} sample meetings.`, 'success');
      refreshConflicts();
      navigate('/');
    } catch (e: any) { notify(e.message || 'Could not load samples.', 'error'); }
    finally { setSeeding(false); }
  }

  const twoCol = running || events.length > 0;

  return (
    <div className="page stack-lg">
      <header>
        <div className="page-eyebrow">Add a meeting</div>
        <h1 className="page-title">Bring a meeting into Tesseract</h1>
        <p className="page-lead">
          Drop in your transcript or recording, or select a pre-loaded sample from <code>data/Demo</code> to watch real-time multi-agent extraction.
        </p>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: twoCol ? '1fr 1fr' : '1.2fr 0.8fr', gap: 20 }}>
        {/* LEFT / PRIMARY MAIN CARD */}
        <div className="card card-pad stack">
          {/* type toggle */}
          <div className="row" style={{ background: 'var(--bg-sunken)', padding: 4, borderRadius: 'var(--r-sm)', gap: 4 }}>
            {(['transcript', 'audio'] as const).map((k) => (
              <button key={k} className="btn btn-sm grow" disabled={running}
                onClick={() => { setKind(k); setFile(null); setSelectedPresetId(null); }}
                style={{ background: kind === k ? 'var(--surface)' : 'transparent', border: kind === k ? '1px solid var(--border-strong)' : '1px solid transparent', color: 'var(--text)' }}>
                {k === 'transcript' ? <FileText size={15} /> : <AudioLines size={15} />}
                {k === 'transcript' ? 'Transcript' : 'Recording'}
              </button>
            ))}
          </div>

          {/* dropzone */}
          <div {...getRootProps()} style={{
            border: `1.5px dashed ${isDragActive ? 'var(--accent)' : selectedPresetId ? 'var(--green)' : 'var(--border-strong)'}`,
            borderRadius: 'var(--r-md)', padding: '30px 20px', textAlign: 'center',
            cursor: running ? 'not-allowed' : 'pointer',
            background: isDragActive ? 'var(--accent-soft)' : selectedPresetId ? 'var(--green-soft)' : 'var(--bg-sunken)',
            transition: 'all 0.2s ease',
          }}>
            <input {...getInputProps()} disabled={running} />
            <div className="empty-icon" style={{ margin: '0 auto 12px' }}>
              <UploadCloud size={22} color={selectedPresetId ? 'var(--green)' : isDragActive ? 'var(--accent)' : 'var(--text-muted)'} />
            </div>
            {file ? (
              <>
                <div style={{ fontWeight: 650, color: selectedPresetId ? 'var(--green)' : 'var(--text)' }}>
                  {selectedPresetId ? `[Preset Loaded] ${file.name}` : file.name}
                </div>
                <div className="muted" style={{ fontSize: 12.5, marginTop: 2 }}>
                  {(file.size / 1024).toFixed(1)} KB · Ready to process
                </div>
              </>
            ) : (
              <>
                <div style={{ fontWeight: 550 }}>
                  Drop your {kind === 'transcript' ? 'transcript' : 'recording'} here, or <span style={{ color: 'var(--accent)' }}>browse</span>
                </div>
                <div className="muted" style={{ fontSize: 12.5, marginTop: 3 }}>
                  {kind === 'transcript' ? 'Text files (.txt, .md)' : 'Audio files (.mp3, .wav, .m4a)'}
                </div>
              </>
            )}
          </div>

          <div className="col" style={{ gap: 6 }}>
            <label className="muted" style={{ fontSize: 12.5, fontWeight: 600 }}>Meeting Identifier</label>
            <input className="input" placeholder="e.g. meeting_01_kickoff" value={meetingId} disabled={running}
              onChange={(e) => setMeetingId(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, '_'))} />
          </div>

          {running ? (
            <button className="btn btn-danger btn-block" onClick={() => { cancelRef.current?.(); setRunning(false); setError('Cancelled.'); }}>
              Stop processing
            </button>
          ) : (
            <button className="btn btn-primary btn-block" disabled={!file} onClick={start}>
              <Play size={15} /> Process this meeting
            </button>
          )}
        </div>

        {/* RIGHT PANEL: DEMO PRESET SELECTOR (OR PROCESSING VIEW WHEN RUNNING) */}
        {twoCol ? (
          <div className="card card-pad stack">
            <div>
              <h3 style={{ fontSize: 15 }}>Pipeline Progress</h3>
              <p className="muted" style={{ fontSize: 13 }}>Following along as Tesseract agents read and reason over the meeting.</p>
            </div>
            <StageProgress events={events} />
            {error && (
              <div className="row" style={{ gap: 9, padding: 12, borderRadius: 'var(--r-md)', background: 'var(--red-soft)', color: 'var(--red)', alignItems: 'flex-start' }}>
                <AlertCircle size={18} style={{ flex: 'none', marginTop: 1 }} />
                <div><div style={{ fontWeight: 600 }}>Couldn’t finish</div><div style={{ fontSize: 13 }}>{error}</div></div>
              </div>
            )}
            {done && (
              <div className="row" style={{ gap: 9, padding: 12, borderRadius: 'var(--r-md)', background: 'var(--green-soft)', color: 'var(--green)', alignItems: 'flex-start' }}>
                <CheckCircle2 size={18} style={{ flex: 'none', marginTop: 1 }} />
                <div className="grow">
                  <div style={{ fontWeight: 600 }}>Done</div>
                  <div style={{ fontSize: 13 }}>Your briefing and knowledge graph are updated.</div>
                  <button className="btn btn-outline btn-sm" style={{ marginTop: 10 }} onClick={() => navigate('/')}>
                    Go to Command Center <ArrowRight size={14} />
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="card card-pad stack">
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
              <div className="row" style={{ gap: 6, alignItems: 'center' }}>
                <FolderOpen size={16} color="var(--accent)" />
                <h3 style={{ fontSize: 15, fontWeight: 650 }}>Demo Presets</h3>
              </div>
            </div>

            <p className="muted" style={{ fontSize: 12.5 }}>
              Click any pre-bundled demo file below to auto-load it into the processor:
            </p>

            <div className="stack" style={{ gap: 8, maxHeight: 380, overflowY: 'auto', paddingRight: 4 }}>
              {DEMO_PRESETS.map((preset) => {
                const isSelected = selectedPresetId === preset.id;
                return (
                  <div
                    key={preset.id}
                    onClick={() => selectPreset(preset)}
                    style={{
                      padding: '10px 12px',
                      borderRadius: 'var(--r-sm)',
                      border: `1px solid ${isSelected ? 'var(--green)' : 'var(--border)'}`,
                      background: isSelected ? 'var(--green-soft)' : 'var(--bg-sunken)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                    className="preset-item"
                  >
                    <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                      <div className="row" style={{ gap: 6, alignItems: 'center' }}>
                        {preset.kind === 'audio' ? <AudioLines size={14} color="var(--amber)" /> : <FileText size={14} color="var(--accent)" />}
                        <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text)' }}>{preset.name}</span>
                      </div>
                      {isSelected && <Zap size={13} color="var(--green)" />}
                    </div>
                    <div className="muted" style={{ fontSize: 11.5, marginTop: 4 }}>
                      {preset.description}
                    </div>
                  </div>
                );
              })}
            </div>

            <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12, marginTop: 4 }}>
              <button className="btn btn-ghost btn-sm btn-block" onClick={seed} disabled={seeding}>
                {seeding ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />} Load All Demo Samples at Once
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
