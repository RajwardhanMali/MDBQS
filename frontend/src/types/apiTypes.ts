export interface QueryRequest {
  user_id: string;
  nl_query: string;
  context: Record<string, unknown>;
}

export interface Customer {
  id?: string;
  customer_id?: string;
  name?: string;
  email?: string;
  [key: string]: unknown;
}

export interface Order {
  order_id?: string;
  customer_id?: string;
  amount?: number;
  order_date?: string;
  [key: string]: unknown;
}

export interface Referral {
  id?: string;
  name?: string;
  email?: string;
  relationship?: string;
  [key: string]: unknown;
}

export interface SimilarCustomer {
  metadata?: {
    name?: string;
    email?: string;
    [key: string]: unknown;
  };
  score?: number;
  distance?: number;
  [key: string]: unknown;
}

export interface ProvenanceEntry {
  source?: string;
  meta?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface FusedData {
  customer?: Customer;
  customers?: Customer[];
  recent_orders?: Order[];
  referrals?: Referral[];
  similar_customers?: SimilarCustomer[];
  explain?: string[];
  provenance?: Record<string, ProvenanceEntry | ProvenanceEntry[] | unknown>;
  [key: string]: unknown;
}

export interface QueryResponse {
  request_id: string;
  status: string;
  fused_data: FusedData;
  explain?: string[];
  [key: string]: unknown;
}

export interface ResultSet {
  key: string;
  server_id: string;
  tool_name: string;
  items: Record<string, unknown>[];
  meta: Record<string, unknown>;
}

export interface Citation {
  server_id: string;
  tool_name: string;
  key: string;
  count: number;
}

export interface TraceShape {
  plan: Record<string, unknown>[];
  tool_calls: Record<string, unknown>[];
  errors: Record<string, unknown>[];
  timings?: Record<string, unknown>;
}

export interface ChatAnswerPayload {
  answer: string;
  result_sets: ResultSet[];
  citations: Citation[];
  explain: string[];
  trace: TraceShape;
}

export interface ChatMessage {
  message_id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  answer_payload?: ChatAnswerPayload;
  created_at: string;
}

export interface ChatSession {
  session_id: string;
  user_id: string;
  title: string;
  summary: string;
  active_server_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface SourceTool {
  name: string;
  description?: string;
  input_schema?: Record<string, unknown>;
}

export interface SourceResource {
  uri: string;
  name: string;
  description?: string;
  mime_type: string;
}

export interface Source {
  server_id: string;
  transport: string;
  base_url: string;
  capabilities: string[];
  tools: SourceTool[];
  resources: SourceResource[];
  health: string;
  metadata: Record<string, unknown>;
}

export interface SchemaSuggestion {
  id: string;
  text: string;
  source?: string;
  entity?: string;
  field?: string;
  field_type?: string;
  score?: number;
}

export interface RunTrace {
  trace_id: string;
  session_id: string;
  message_id: string;
  plan: Record<string, unknown>[];
  tool_calls: Record<string, unknown>[];
  errors: Record<string, unknown>[];
  timings?: Record<string, unknown>;
  created_at: string;
}

export interface HistoryItem {
  id: string;
  query: string;
  timestamp: number;
  result?: QueryResponse;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  timestamp: number;
  result?: QueryResponse;
  error?: string;
}

export interface CreateSessionRequest {
  user_id: string;
  title?: string;
  source_ids: string[];
}

export interface ChatRequest {
  session_id: string;
  user_id: string;
  message: string;
  source_ids: string[];
}

export interface ChatResponse extends ChatAnswerPayload {
  session_id: string;
  message_id: string;
}
