import axios from 'axios';
import {
  ChatRequest,
  ChatResponse,
  ChatSession,
  CreateSessionRequest,
  RunTrace,
  SchemaSuggestion,
  Source,
  ChatMessage,
} from '../types/apiTypes';

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

const fallbackSuggestions: SchemaSuggestion[] = [
  {
    id: 'connected-sources',
    text: 'Browse connected sources',
    source: 'workspace',
  },
  {
    id: 'schema-search',
    text: 'Search schema fields before asking',
    source: 'workspace',
  },
];

const normalizeSuggestion = (hit: unknown, index: number): SchemaSuggestion | null => {
  if (!hit || typeof hit !== 'object') {
    return null;
  }

  const value = hit as Record<string, unknown>;
  const source = typeof value.mcp === 'string' ? value.mcp : typeof value.server_id === 'string' ? value.server_id : undefined;
  const entity = typeof value.parent === 'string' ? value.parent : typeof value.entity === 'string' ? value.entity : undefined;
  const field = typeof value.field === 'string' ? value.field : undefined;
  const fieldType = typeof value.field_type === 'string' ? value.field_type : undefined;
  const id = typeof value.id === 'string' ? value.id : `${source ?? 'schema'}-${entity ?? 'entity'}-${field ?? index}`;
  const text = [source, entity, field].filter(Boolean).join(' / ');

  return {
    id,
    text: text || id,
    source,
    entity,
    field,
    field_type: fieldType,
    score: typeof value.score === 'number' ? value.score : undefined,
  };
};

export const chatApi = {
  async createSession(request: CreateSessionRequest): Promise<ChatSession> {
    const response = await client.post<ChatSession>('/sessions', request);
    return response.data;
  },

  async getSession(sessionId: string): Promise<ChatSession> {
    const response = await client.get<ChatSession>(`/sessions/${sessionId}`);
    return response.data;
  },

  async getSessionMessages(sessionId: string): Promise<{ session_id: string; messages: ChatMessage[] }> {
    const response = await client.get<{ session_id: string; messages: ChatMessage[] }>(`/sessions/${sessionId}/messages`);
    return response.data;
  },

  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await client.post<ChatResponse>('/chat', request);
    return response.data;
  },

  async listSources(): Promise<Source[]> {
    const response = await client.get<{ sources: Source[] }>('/sources');
    return response.data.sources ?? [];
  },

  async getSource(serverId: string): Promise<Source> {
    const response = await client.get<Source>(`/sources/${serverId}`);
    return response.data;
  },

  async getRunTrace(messageId: string): Promise<RunTrace> {
    const response = await client.get<RunTrace>(`/runs/${messageId}`);
    return response.data;
  },

  async searchSchema(query: string): Promise<SchemaSuggestion[]> {
    const trimmed = query.trim();
    if (!trimmed) {
      return [];
    }

    try {
      const response = await client.get<{ hits?: unknown[] }>('/schema/search', {
        params: { q: trimmed },
        timeout: 5000,
      });

      const normalized = (response.data.hits ?? [])
        .map((hit, index) => normalizeSuggestion(hit, index))
        .filter((item): item is SchemaSuggestion => Boolean(item));

      return normalized.length > 0 ? normalized : fallbackSuggestions;
    } catch {
      return fallbackSuggestions;
    }
  },
};
