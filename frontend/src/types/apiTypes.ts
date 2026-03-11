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

export interface SchemaSuggestion {
  text: string;
  source?: string;
  entity?: string;
  field?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  timestamp: number;
  result?: QueryResponse;
  error?: string;
}

export interface HistoryItem {
  id: string;
  query: string;
  timestamp: number;
  result?: QueryResponse;
}
