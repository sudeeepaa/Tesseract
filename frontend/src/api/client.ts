/**
 * Threadline API client.
 * Connects the React frontend to the FastAPI backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface Decision {
  id: string;
  text: string;
  status: 'proposed' | 'confirmed' | 'under_review' | 'superseded' | 'reversed';
  rationale?: string;
  owner?: string;
  source_meeting_id: string;
  supersedes_decision_id?: string;
  contradicts_decision_ids?: string[];
}

export interface ActionItem {
  id: string;
  text: string;
  assignee?: string;
  due_date?: string;
  status: 'open' | 'in_progress' | 'completed' | 'cancelled';
  source_meeting_id: string;
  completed_meeting_id?: string;
}

export interface ConflictRecord {
  id: string;
  fact_a_id: string;
  fact_b_id: string;
  fact_a_text: string;
  fact_b_text: string;
  description: string;
  meeting_a_id: string;
  meeting_b_id: string;
  resolved: boolean;
  resolution_meeting_id?: string;
  confidence?: number;
  reasoning?: string;
  resolution_choice?: string;
  resolution_note?: string;
  resolved_by?: string;
  resolved_at?: string;
}

export type ResolutionChoice = 'keep' | 'switch' | 'review' | 'dismiss';

export interface ConflictResolutionRequest {
  choice: ResolutionChoice;
  note?: string;
  resolved_by?: string;
  keep_decision_id?: string;
  supersede_decision_id?: string;
}

export interface ConflictsResponse {
  conflicts: ConflictRecord[];
  unresolved_count: number;
  total_count: number;
}

export interface BriefingOutput {
  generated_at: string;
  meeting_count: number;
  decisions: Decision[];
  action_items: ActionItem[];
  conflicts: ConflictRecord[];
  topics: string[];
  markdown: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: 'meeting' | 'decision' | 'action_item' | 'entity' | 'topic';
  properties: Record<string, any>;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: 'SUPERSEDES' | 'CONTRADICTS' | 'MENTIONED_IN' | 'ASSIGNED_TO' | 'RELATED_TO' | 'RESOLVES';
  superseded: boolean;
  properties: Record<string, any>;
}

export interface GraphSnapshot {
  nodes: GraphNode[];
  edges: GraphEdge[];
  generated_at: string;
}

export interface SearchResult {
  fact_id: string;
  text: string;
  score: number;
  meeting_id: string;
  speaker?: string;
  fact_type: 'decision' | 'action_item' | 'entity' | 'topic' | 'general';
}

export interface SearchResponse {
  results: SearchResult[];
  answer?: string | null;
  grounded?: boolean;   // false → meetings don't cover the query; hide the matches
}

export interface MeetingSummary {
  id: string;
  title: string;
  recorded_at?: string | null;
  ingested_at?: string | null;
  decision_count: number;
  action_item_count: number;
  topic_count: number;
  preview?: string | null;
  summary?: string | null;   // cached at ingestion; present without a second call
}

export interface MeetingsResponse {
  meetings: MeetingSummary[];
  count: number;
}

export interface MeetingSummaryResponse {
  meeting_id: string;
  title: string;
  summary_markdown: string;
}

export interface BackendStatus {
  neo4j: {
    connected: boolean;
    node_count: number;
    edge_count: number;
    backend: 'neo4j' | 'memory';
    error?: string;
  };
  qdrant: {
    connected: boolean;
    vector_count: number;
    backend: 'qdrant' | 'memory';
    error?: string;
  };
  llm: {
    backend: 'openai' | 'gemini' | 'mock';
  };
}

export interface PipelineStageEvent {
  stage: 'INGEST' | 'TRANSCRIBE' | 'EXTRACT' | 'GRAPH_WRITE' | 'VECTOR_WRITE' | 'BRIEFING' | 'PIPELINE';
  status: 'pending' | 'running' | 'done' | 'error' | 'skipped';
  message: string;
  data?: Record<string, any>;
}

export const apiClient = {
  getApiUrl(path: string): string {
    return `${API_BASE_URL}${path}`;
  },

  async getStatus(): Promise<BackendStatus> {
    const res = await fetch(`${API_BASE_URL}/api/v1/status`);
    if (!res.ok) throw new Error('Failed to fetch status');
    return res.json();
  },

  async getBriefing(): Promise<BriefingOutput> {
    const res = await fetch(`${API_BASE_URL}/api/v1/briefing`);
    if (!res.ok) throw new Error('Failed to fetch briefing');
    return res.json();
  },

  async getGraph(): Promise<GraphSnapshot> {
    const res = await fetch(`${API_BASE_URL}/api/v1/graph`);
    if (!res.ok) throw new Error('Failed to fetch graph snapshot');
    return res.json();
  },

  async search(query: string, topK: number = 5): Promise<SearchResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, top_k: topK })
    });
    if (!res.ok) throw new Error('Failed to execute search');
    return res.json();
  },

  async getSearchSuggestions(): Promise<string[]> {
    const res = await fetch(`${API_BASE_URL}/api/v1/search/suggestions`);
    if (!res.ok) throw new Error('Failed to load suggestions');
    return (await res.json()).questions ?? [];
  },

  async listMeetings(): Promise<MeetingsResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/meetings`);
    if (!res.ok) throw new Error('Failed to load meetings');
    return res.json();
  },

  async getMeetingSummary(meetingId: string): Promise<MeetingSummaryResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/meetings/${encodeURIComponent(meetingId)}/summary`);
    if (!res.ok) throw new Error('Failed to generate meeting summary');
    return res.json();
  },

  async listConflicts(): Promise<ConflictsResponse> {
    const res = await fetch(`${API_BASE_URL}/api/v1/conflicts`);
    if (!res.ok) throw new Error('Failed to fetch conflicts');
    return res.json();
  },

  async resolveConflict(
    conflictId: string,
    body: ConflictResolutionRequest
  ): Promise<{ status: string; conflict: ConflictRecord | null }> {
    const res = await fetch(
      `${API_BASE_URL}/api/v1/conflicts/${encodeURIComponent(conflictId)}/resolve`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }
    );
    if (!res.ok) {
      const msg = res.status === 404 ? 'That conflict no longer exists.' : 'Could not save your decision.';
      throw new Error(msg);
    }
    return res.json();
  },

  async purgePerson(name: string): Promise<any> {
    const res = await fetch(
      `${API_BASE_URL}/api/v1/governance/purge/${encodeURIComponent(name)}`,
      { method: 'DELETE' }
    );
    if (!res.ok) throw new Error('Failed to remove person');
    return res.json();
  },

  async seedSampleMeetings(): Promise<{ meetings_loaded: number }> {
    const res = await fetch(`${API_BASE_URL}/api/v1/demo/seed`, { method: 'POST' });
    if (!res.ok) throw new Error('Could not load the sample meetings');
    return res.json();
  },

  /**
   * Run the pipeline and return an EventSource connection.
   * Note: The caller must invoke close() on the returned EventSource when done listening.
   */
  runPipelineStream(
    file: File,
    meetingId?: string,
    onMessage?: (event: PipelineStageEvent) => void,
    onError?: (error: any) => void
  ): { cancel: () => void } {
    const formData = new FormData();
    formData.append('file', file);
    if (meetingId) {
      formData.append('meeting_id', meetingId);
    }

    // Since EventSource only supports GET by default, FastAPI run endpoint handles POST.
    // Instead of raw EventSource for the initiator POST, we can either:
    // (a) Use fetch to POST, and have the backend return SSE stream, which we read using Response.body.getReader().
    // This is the standard, clean, modern way to do POST-based streaming in browsers!
    const controller = new AbortController();
    const state = { active: true };

    (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/pipeline/run`, {
          method: 'POST',
          body: formData,
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Pipeline initialization failed: ${response.statusText}`);
        }

        const ctype = response.headers.get('content-type') || '';

        // Audio path: the backend accepts the job (202 + JSON) and transcribes
        // in the background. Poll the status endpoint instead of reading SSE.
        if (response.status === 202 || ctype.includes('application/json')) {
          const info = await response.json();
          const mid = info.meeting_id || meetingId || '';
          await pollJobStatus(mid, controller.signal, state, onMessage);
          return;
        }

        // Text path: server streams one SSE event per pipeline stage.
        const reader = response.body?.getReader();
        if (!reader) throw new Error('Response body is not readable');

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith('data: ')) {
              try {
                const parsed: PipelineStageEvent = jsonParseSafely(trimmed.slice(6));
                if (onMessage) onMessage(parsed);
              } catch (e) {
                console.error('Error parsing SSE event:', e);
              }
            }
          }
        }
      } catch (err: any) {
        if (err.name !== 'AbortError' && onError) {
          onError(err);
        }
      }
    })();

    return {
      cancel: () => { state.active = false; controller.abort(); }
    };
  }
};

/**
 * Poll a background (audio) pipeline job and surface each new stage event once.
 */
async function pollJobStatus(
  meetingId: string,
  signal: AbortSignal,
  state: { active: boolean },
  onMessage?: (event: PipelineStageEvent) => void
): Promise<void> {
  const seen = new Set<string>();
  while (state.active && !signal.aborted) {
    await new Promise((r) => setTimeout(r, 1200));
    if (!state.active || signal.aborted) return;

    let job: any;
    try {
      const r = await fetch(
        `${API_BASE_URL}/api/v1/pipeline/status/${encodeURIComponent(meetingId)}`,
        { signal }
      );
      if (!r.ok) continue;
      job = await r.json();
    } catch {
      if (signal.aborted) return;
      continue;
    }

    const events: PipelineStageEvent[] = job.events || [];
    for (const ev of events) {
      const key = `${ev.stage}:${ev.status}`;
      if (!seen.has(key)) { seen.add(key); onMessage?.(ev); }
    }

    if (job.status === 'COMPLETED' || job.status === 'FAILED') {
      const hasTerminal = events.some((e) => e.stage === 'PIPELINE');
      if (!hasTerminal) {
        onMessage?.({
          stage: 'PIPELINE',
          status: job.status === 'COMPLETED' ? 'done' : 'error',
          message: job.progress || (job.status === 'COMPLETED' ? 'Done' : 'Processing failed'),
        });
      }
      return;
    }
  }
}

function jsonParseSafely(str: string): any {
  try {
    return JSON.parse(str);
  } catch (e) {
    return { stage: 'PIPELINE', status: 'error', message: `Parse error: ${str}` };
  }
}
