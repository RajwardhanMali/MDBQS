import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { queryApi } from '../api/queryApi';
import { HistoryItem, Message, QueryResponse, SchemaSuggestion } from '../types/apiTypes';

interface ChatState {
  messages: Message[];
  history: HistoryItem[];
  suggestions: SchemaSuggestion[];
  loading: boolean;
}

interface ChatActions {
  submitQuery: (query: string) => Promise<void>;
  fetchSuggestions: (query: string) => Promise<void>;
  clearSuggestions: () => void;
  clearChat: () => void;
  loadHistoryItem: (id: string) => void;
  deleteHistoryItem: (id: string) => void;
}

type ChatStore = ChatState & ChatActions;

const MAX_HISTORY = 100;

const assistantError = (message: string): Message => ({
  id: crypto.randomUUID(),
  role: 'assistant',
  text: 'Sorry, something went wrong while processing your query.',
  timestamp: Date.now(),
  error: message,
});

const assistantResult = (result: QueryResponse): Message => ({
  id: crypto.randomUUID(),
  role: 'assistant',
  text: 'Here are the fused results from your databases.',
  timestamp: Date.now(),
  result,
});

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      messages: [],
      history: [],
      suggestions: [],
      loading: false,

      submitQuery: async (query: string) => {
        const trimmed = query.trim();
        if (!trimmed || get().loading) {
          return;
        }

        const userMessage: Message = {
          id: crypto.randomUUID(),
          role: 'user',
          text: trimmed,
          timestamp: Date.now(),
        };

        set((state) => ({
          loading: true,
          messages: [...state.messages, userMessage],
          suggestions: [],
        }));

        try {
          const result = await queryApi.submitQuery({
            user_id: 'u1',
            nl_query: trimmed,
            context: {},
          });

          const safeResult: QueryResponse = {
            ...result,
            fused_data: result.fused_data ?? {},
          };

          set((state) => ({
            loading: false,
            messages: [...state.messages, assistantResult(safeResult)],
            history: [
              {
                id: crypto.randomUUID(),
                query: trimmed,
                timestamp: Date.now(),
                result: safeResult,
              },
              ...state.history,
            ].slice(0, MAX_HISTORY),
          }));
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Unknown error';
          set((state) => ({
            loading: false,
            messages: [...state.messages, assistantError(message)],
            history: [
              {
                id: crypto.randomUUID(),
                query: trimmed,
                timestamp: Date.now(),
              },
              ...state.history,
            ].slice(0, MAX_HISTORY),
          }));
        }
      },

      fetchSuggestions: async (query: string) => {
        const trimmed = query.trim();
        if (trimmed.length < 2) {
          set({ suggestions: [] });
          return;
        }

        const suggestions = await queryApi.searchSchema(trimmed);
        set({ suggestions });
      },

      clearSuggestions: () => set({ suggestions: [] }),

      clearChat: () => set({ messages: [], suggestions: [] }),

      loadHistoryItem: (id: string) => {
        const item = get().history.find((entry) => entry.id === id);
        if (!item) {
          return;
        }

        const replay: Message[] = [
          {
            id: crypto.randomUUID(),
            role: 'user',
            text: item.query,
            timestamp: item.timestamp,
          },
        ];

        if (item.result) {
          replay.push(assistantResult(item.result));
        }

        set({ messages: replay });
      },

      deleteHistoryItem: (id: string) => {
        set((state) => ({
          history: state.history.filter((entry) => entry.id !== id),
        }));
      },
    }),
    {
      name: 'mdbqs-chat-store',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        history: state.history,
      }),
    }
  )
);
