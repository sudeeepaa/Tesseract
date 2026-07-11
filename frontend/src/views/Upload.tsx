import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, AudioLines, Play, AlertCircle, Sparkles, CheckCircle } from 'lucide-react';
import { apiClient, PipelineStageEvent } from '../api/client';
import { StageProgress } from '../components/StageProgress';

interface UploadViewProps {
  onPipelineSuccess: () => void;
}

export const UploadView: React.FC<UploadViewProps> = ({ onPipelineSuccess }) => {
  const [file, setFile] = useState<File | null>(null);
  const [meetingId, setMeetingId] = useState<string>('');
  const [uploadType, setUploadType] = useState<'transcript' | 'audio'>('transcript');
  
  // Pipeline tracking state
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [events, setEvents] = useState<PipelineStageEvent[]>([]);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [pipelineSuccess, setPipelineSuccess] = useState<boolean>(false);
  const [cancelStream, setCancelStream] = useState<(() => void) | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const selected = acceptedFiles[0];
      const lastDot = selected.name.lastIndexOf('.');
      const defaultId = lastDot > 0 ? selected.name.substring(0, lastDot) : selected.name;
      setFile(selected);
      setMeetingId(defaultId.toLowerCase().replace(/[^a-z0-9_-]/g, '_'));
      
      // Auto-detect upload type based on file extension
      const ext = selected.name.split('.').pop()?.toLowerCase();
      if (ext && ['mp3', 'wav', 'm4a', 'mp4', 'ogg', 'webm'].includes(ext)) {
        setUploadType('audio');
      } else {
        setUploadType('transcript');
      }
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    maxFiles: 1,
    accept: uploadType === 'transcript' 
      ? { 'text/plain': ['.txt'], 'text/markdown': ['.md'] }
      : { 'audio/*': ['.mp3', '.wav', '.m4a', '.mp4', '.ogg', '.webm'] }
  });

  const handleStartPipeline = () => {
    if (!file) return;

    // Reset state
    setIsRunning(true);
    setPipelineSuccess(false);
    setPipelineError(null);
    setEvents([]);

    const stream = apiClient.runPipelineStream(
      file,
      meetingId || undefined,
      (event) => {
        // Append new events or update state
        setEvents((prev) => {
          // If stage event already exists, replace it, otherwise append
          const idx = prev.findIndex((e) => e.stage === event.stage);
          if (idx >= 0) {
            const updated = [...prev];
            updated[idx] = event;
            return updated;
          }
          return [...prev, event];
        });

        if (event.stage === 'PIPELINE') {
          if (event.status === 'done') {
            setPipelineSuccess(true);
            setIsRunning(false);
            onPipelineSuccess();
          } else if (event.status === 'error') {
            setPipelineError(event.message);
            setIsRunning(false);
          }
        }
      },
      (error) => {
        console.error('Streaming error:', error);
        setPipelineError(error.message || 'Stream connection failed');
        setIsRunning(false);
      }
    );

    setCancelStream(() => stream.cancel);
  };

  const handleCancel = () => {
    if (cancelStream) {
      cancelStream();
    }
    setIsRunning(false);
    setPipelineError('Pipeline cancelled by user');
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: isRunning || events.length > 0 ? '1fr 1fr' : '1fr', gap: '2rem', transition: 'all 0.5s ease' }}>
      {/* Configuration & Drag zone Panel */}
      <div className="glass-panel" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Sparkles color="var(--secondary)" size={24} />
            Ingest New Meeting
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
            Upload raw text transcripts or audio recordings to process facts, conflicts, and decisions.
          </p>
        </div>

        {/* Upload type selection */}
        <div style={{ display: 'flex', gap: '1rem', backgroundColor: 'rgba(0, 0, 0, 0.2)', padding: '0.25rem', borderRadius: 'var(--radius-sm)' }}>
          <button 
            type="button"
            onClick={() => { if (!isRunning) { setUploadType('transcript'); setFile(null); } }}
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
              padding: '0.6rem',
              border: 'none',
              borderRadius: '4px',
              cursor: isRunning ? 'not-allowed' : 'pointer',
              backgroundColor: uploadType === 'transcript' ? 'var(--primary)' : 'transparent',
              color: uploadType === 'transcript' ? '#fff' : 'var(--text-secondary)',
              fontWeight: 600,
              fontSize: '0.9rem',
              transition: 'var(--transition-smooth)'
            }}
          >
            <FileText size={16} />
            Transcript (Recommended)
          </button>
          <button 
            type="button"
            onClick={() => { if (!isRunning) { setUploadType('audio'); setFile(null); } }}
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
              padding: '0.6rem',
              border: 'none',
              borderRadius: '4px',
              cursor: isRunning ? 'not-allowed' : 'pointer',
              backgroundColor: uploadType === 'audio' ? 'var(--primary)' : 'transparent',
              color: uploadType === 'audio' ? '#fff' : 'var(--text-secondary)',
              fontWeight: 600,
              fontSize: '0.9rem',
              transition: 'var(--transition-smooth)'
            }}
          >
            <AudioLines size={16} />
            Audio (Best-Effort API)
          </button>
        </div>

        {/* Drag and Drop Zone */}
        <div 
          {...getRootProps()} 
          style={{
            border: '2px dashed var(--border-glass)',
            borderRadius: 'var(--radius-md)',
            padding: '3rem 2rem',
            textAlign: 'center',
            cursor: isRunning ? 'not-allowed' : 'pointer',
            backgroundColor: isDragActive ? 'rgba(79, 70, 229, 0.05)' : 'rgba(0, 0, 0, 0.1)',
            borderColor: isDragActive ? 'var(--primary)' : 'var(--border-glass)',
            transition: 'var(--transition-smooth)'
          }}
        >
          <input {...getInputProps()} disabled={isRunning} />
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
            <div style={{ padding: '1rem', borderRadius: '50%', backgroundColor: 'rgba(255, 255, 255, 0.03)' }}>
              <Upload size={32} color={isDragActive ? 'var(--primary)' : 'var(--text-secondary)'} />
            </div>
            {file ? (
              <div>
                <p style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{file.name}</p>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                  {(file.size / 1024).toFixed(1)} KB
                </p>
              </div>
            ) : (
              <div>
                <p style={{ fontWeight: 500, fontSize: '0.95rem' }}>
                  Drag & drop your {uploadType} file here, or <span style={{ color: 'var(--secondary)', textDecoration: 'underline' }}>browse</span>
                </p>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>
                  {uploadType === 'transcript' ? 'Supports .txt and .md files' : 'Supports .mp3, .wav, .m4a files'}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Inputs */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
            MEETING ID OVERRIDE (OPTIONAL)
          </label>
          <input 
            type="text" 
            placeholder="e.g. meeting_01" 
            value={meetingId}
            onChange={(e) => setMeetingId(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, '_'))}
            disabled={isRunning}
            style={{
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-glass)',
              backgroundColor: 'rgba(0, 0, 0, 0.3)',
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-mono)',
              outline: 'none',
              fontSize: '0.9rem'
            }}
          />
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
          {isRunning ? (
            <button 
              onClick={handleCancel}
              style={{
                flex: 1,
                padding: '0.8rem',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-error)',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                color: 'var(--color-error)',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '0.95rem'
              }}
            >
              Cancel Processing
            </button>
          ) : (
            <button 
              onClick={handleStartPipeline}
              disabled={!file}
              style={{
                flex: 1,
                padding: '0.8rem',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                backgroundColor: file ? 'var(--primary)' : 'rgba(255, 255, 255, 0.05)',
                color: file ? '#fff' : 'var(--text-muted)',
                cursor: file ? 'pointer' : 'not-allowed',
                fontWeight: 600,
                fontSize: '0.95rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                boxShadow: file ? '0 4px 15px var(--primary-glow)' : 'none',
                transition: 'var(--transition-smooth)'
              }}
            >
              <Play size={16} fill="currentColor" />
              Analyze Transcript
            </button>
          )}
        </div>
      </div>

      {/* Progress & SSE Streaming Stepper Panel */}
      {(isRunning || events.length > 0) && (
        <div className="glass-panel" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div>
            <h3 style={{ fontSize: '1.25rem', marginBottom: '0.25rem' }}>Analysis Pipeline Progress</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              Real-time Server-Sent Events showing status transitions for each stage.
            </p>
          </div>

          <StageProgress events={events} />

          {pipelineError && (
            <div 
              style={{ 
                display: 'flex', 
                gap: '0.75rem', 
                padding: '1rem', 
                borderRadius: 'var(--radius-sm)', 
                backgroundColor: 'rgba(239, 68, 68, 0.08)',
                border: '1px solid rgba(239, 68, 68, 0.2)',
                color: '#f87171',
                fontSize: '0.9rem',
                alignItems: 'flex-start'
              }}
            >
              <AlertCircle size={20} style={{ flexShrink: 0, marginTop: '0.1rem' }} />
              <div>
                <div style={{ fontWeight: 600 }}>Pipeline Error</div>
                <div style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>{pipelineError}</div>
              </div>
            </div>
          )}

          {pipelineSuccess && (
            <div 
              style={{ 
                display: 'flex', 
                gap: '0.75rem', 
                padding: '1rem', 
                borderRadius: 'var(--radius-sm)', 
                backgroundColor: 'rgba(16, 185, 129, 0.08)',
                border: '1px solid rgba(16, 185, 129, 0.2)',
                color: '#34d399',
                fontSize: '0.9rem',
                alignItems: 'flex-start'
              }}
            >
              <CheckCircle size={20} style={{ flexShrink: 0, marginTop: '0.1rem' }} />
              <div>
                <div style={{ fontWeight: 600 }}>Pipeline Complete!</div>
                <div style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>
                  The knowledge graph has been compiled and the briefing is updated. Navigate to the Briefing or Graph page to view results.
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
