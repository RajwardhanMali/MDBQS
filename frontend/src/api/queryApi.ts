import axios from 'axios';
import { QueryRequest, QueryResponse, SchemaSuggestion } from '../types/apiTypes';

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

const fallbackSuggestions: SchemaSuggestion[] = [
  { text: 'Find customer by email', source: 'fallback' },
  { text: 'List all customers', source: 'fallback' },
  { text: 'Show referrals for customer', source: 'fallback' },
  { text: 'Find customers similar to cust010', source: 'fallback' },
];

const normalizeSuggestion = (hit: unknown): SchemaSuggestion | null => {
  if (typeof hit === 'string') {
    return { text: hit };
  }

  if (!hit || typeof hit !== 'object') {
    return null;
  }

  const obj = hit as Record<string, unknown>;
  const source = typeof obj.mcp_id === 'string' ? obj.mcp_id : undefined;
  const entity = typeof obj.entity === 'string' ? obj.entity : undefined;
  const field = typeof obj.field === 'string' ? obj.field : undefined;

  const text = [source, entity, field].filter(Boolean).join(' -> ');
  return { text: text || JSON.stringify(hit), source, entity, field };
};

const filterFallback = (query: string) => {
  const q = query.toLowerCase();
  return fallbackSuggestions.filter((s) => s.text.toLowerCase().includes(q));
};

export const queryApi = {
  async submitQuery(request: QueryRequest): Promise<QueryResponse> {
    const response = await client.post<QueryResponse>('/query', request);
    return response.data;
  },

  async searchSchema(query: string): Promise<SchemaSuggestion[]> {
    const trimmed = query.trim();
    if (!trimmed) {
      return [];
    }

    try {
      const response = await client.get<{ hits?: unknown[]; suggestions?: unknown[] }>('/schema/search', {
        params: { q: trimmed },
        timeout: 5000,
      });

      const rawItems = response.data.hits ?? response.data.suggestions ?? [];
      const normalized = rawItems.map(normalizeSuggestion).filter((item): item is SchemaSuggestion => Boolean(item));
      return normalized.length ? normalized : filterFallback(trimmed);
    } catch {
      return filterFallback(trimmed);
    }
  },
};
