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

        const reader = response.body?.getReader();
        if (!reader) throw new Error('Response body is not readable');

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          // Keep the last partial line in the buffer
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
      cancel: () => controller.abort()
    };
  }
};

function jsonParseSafely(str: string): any {
  try {
    return JSON.parse(str);
  } catch (e) {
    return { stage: 'PIPELINE', status: 'error', message: `Parse error: ${str}` };
  }
}
