import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { chatApi } from '../api/chatApi';
import {
  ChatAnswerPayload,
  ChatMessage,
  ChatSession,
  RunTrace,
  SchemaSuggestion,
  Source,
  TraceShape,
} from '../types/apiTypes';

interface ChatState {
  userId: string;
  sessions: ChatSession[];
  currentSessionId: string | null;
  messagesBySession: Record<string, ChatMessage[]>;
  sources: Source[];
  sourceDetails: Record<string, Source>;
  schemaSuggestions: SchemaSuggestion[];
  runTraces: Record<string, RunTrace>;
  composerDraft: string;
  bootstrapping: boolean;
  sendingMessage: boolean;
  sourcesLoading: boolean;
  schemaLoading: boolean;
  traceLoadingIds: string[];
  error: string | null;
}

interface ChatActions {
  bootstrap: () => Promise<void>;
  createSession: (title?: string) => Promise<void>;
  selectSession: (sessionId: string) => Promise<void>;
  sendMessage: (message: string) => Promise<void>;
  fetchSources: () => Promise<void>;
  fetchSourceDetails: (serverId: string) => Promise<void>;
  toggleSource: (serverId: string) => void;
  searchSchema: (query: string) => Promise<void>;
  clearSchemaSuggestions: () => void;
  loadRunTrace: (messageId: string) => Promise<void>;
  setComposerDraft: (value: string) => void;
}

type ChatStore = ChatState & ChatActions;

const emptyTrace = (): TraceShape => ({
  plan: [],
  tool_calls: [],
  errors: [],
});

const toAssistantPayload = (message: string, traceMessage: string): ChatAnswerPayload => ({
  answer: message,
  result_sets: [],
  citations: [],
  explain: [],
  trace: {
    ...emptyTrace(),
    errors: [{ message: traceMessage }],
  },
});

const upsertSession = (sessions: ChatSession[], session: ChatSession) => {
  const next = sessions.filter((entry) => entry.session_id !== session.session_id);
  return [session, ...next].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
};

const syncSessionState = async (sessionId: string) => {
  const [session, transcript] = await Promise.all([
    chatApi.getSession(sessionId),
    chatApi.getSessionMessages(sessionId),
  ]);

  return {
    session,
    messages: transcript.messages ?? [],
  };
};

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      userId: 'u1',
      sessions: [],
      currentSessionId: null,
      messagesBySession: {},
      sources: [],
      sourceDetails: {},
      schemaSuggestions: [],
      runTraces: {},
      composerDraft: '',
      bootstrapping: false,
      sendingMessage: false,
      sourcesLoading: false,
      schemaLoading: false,
      traceLoadingIds: [],
      error: null,

      bootstrap: async () => {
        if (get().bootstrapping) {
          return;
        }

        set({ bootstrapping: true, error: null });

        try {
          await get().fetchSources();

          const sessionId = get().currentSessionId;
          if (sessionId) {
            try {
              await get().selectSession(sessionId);
            } catch {
              await get().createSession();
            }
          } else {
            await get().createSession();
          }
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Unable to initialize the workspace.';
          set({ error: message });
        } finally {
          set({ bootstrapping: false });
        }
      },

      createSession: async (title) => {
        const { userId, sources } = get();
        const sourceIds = sources.map((source) => source.server_id);
        const session = await chatApi.createSession({
          user_id: userId,
          title,
          source_ids: sourceIds,
        });

        set((state) => ({
          currentSessionId: session.session_id,
          sessions: upsertSession(state.sessions, session),
          messagesBySession: {
            ...state.messagesBySession,
            [session.session_id]: [],
          },
          error: null,
        }));
      },

      selectSession: async (sessionId) => {
        const { session, messages } = await syncSessionState(sessionId);

        set((state) => ({
          currentSessionId: sessionId,
          sessions: upsertSession(state.sessions, session),
          messagesBySession: {
            ...state.messagesBySession,
            [sessionId]: messages,
          },
          error: null,
        }));
      },

      sendMessage: async (message) => {
        const trimmed = message.trim();
        if (!trimmed || get().sendingMessage) {
          return;
        }

        let sessionId = get().currentSessionId;
        if (!sessionId) {
          await get().createSession();
          sessionId = get().currentSessionId;
        }

        if (!sessionId) {
          return;
        }

        const currentSession = get().sessions.find((session) => session.session_id === sessionId);
        const optimisticUser: ChatMessage = {
          message_id: `local-user-${crypto.randomUUID()}`,
          session_id: sessionId,
          role: 'user',
          content: trimmed,
          created_at: new Date().toISOString(),
        };

        set((state) => ({
          sendingMessage: true,
          composerDraft: '',
          schemaSuggestions: [],
          messagesBySession: {
            ...state.messagesBySession,
            [sessionId as string]: [...(state.messagesBySession[sessionId as string] ?? []), optimisticUser],
          },
          error: null,
        }));

        try {
          await chatApi.sendMessage({
            session_id: sessionId,
            user_id: get().userId,
            message: trimmed,
            source_ids: currentSession?.active_server_ids ?? [],
          });
          const { session, messages } = await syncSessionState(sessionId);

          set((state) => ({
            sendingMessage: false,
            sessions: upsertSession(state.sessions, session),
            messagesBySession: {
              ...state.messagesBySession,
              [sessionId as string]: messages,
            },
          }));
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'The assistant could not complete that request.';
          const assistant: ChatMessage = {
            message_id: `local-assistant-${crypto.randomUUID()}`,
            session_id: sessionId,
            role: 'assistant',
            content: 'The request did not complete successfully.',
            answer_payload: toAssistantPayload('The request did not complete successfully.', errorMessage),
            created_at: new Date().toISOString(),
          };

          set((state) => ({
            sendingMessage: false,
            error: errorMessage,
            messagesBySession: {
              ...state.messagesBySession,
              [sessionId as string]: [...(state.messagesBySession[sessionId as string] ?? []), assistant],
            },
          }));
        }
      },

      fetchSources: async () => {
        if (get().sourcesLoading) {
          return;
        }

        set({ sourcesLoading: true });
        try {
          const sources = await chatApi.listSources();
          set({ sources, error: null });
        } finally {
          set({ sourcesLoading: false });
        }
      },

      fetchSourceDetails: async (serverId) => {
        if (get().sourceDetails[serverId]) {
          return;
        }

        const source = await chatApi.getSource(serverId);
        set((state) => ({
          sourceDetails: {
            ...state.sourceDetails,
            [serverId]: source,
          },
        }));
      },

      toggleSource: (serverId) => {
        const currentSessionId = get().currentSessionId;
        if (!currentSessionId) {
          return;
        }

        set((state) => ({
          sessions: state.sessions.map((session) => {
            if (session.session_id !== currentSessionId) {
              return session;
            }

            const exists = session.active_server_ids.includes(serverId);
            return {
              ...session,
              active_server_ids: exists
                ? session.active_server_ids.filter((id) => id !== serverId)
                : [...session.active_server_ids, serverId],
            };
          }),
        }));
      },

      searchSchema: async (query) => {
        const trimmed = query.trim();
        if (trimmed.length < 2) {
          set({ schemaSuggestions: [], schemaLoading: false });
          return;
        }

        set({ schemaLoading: true });
        try {
          const schemaSuggestions = await chatApi.searchSchema(trimmed);
          set({ schemaSuggestions, error: null });
        } finally {
          set({ schemaLoading: false });
        }
      },

      clearSchemaSuggestions: () => set({ schemaSuggestions: [] }),

      loadRunTrace: async (messageId) => {
        if (get().runTraces[messageId] || get().traceLoadingIds.includes(messageId)) {
          return;
        }

        set((state) => ({ traceLoadingIds: [...state.traceLoadingIds, messageId] }));
        try {
          const trace = await chatApi.getRunTrace(messageId);
          set((state) => ({
            runTraces: {
              ...state.runTraces,
              [messageId]: trace,
            },
          }));
        } finally {
          set((state) => ({
            traceLoadingIds: state.traceLoadingIds.filter((id) => id !== messageId),
          }));
        }
      },

      setComposerDraft: (value) => set({ composerDraft: value }),
    }),
    {
      name: 'mdbqs-chat-store',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        sessions: state.sessions,
        currentSessionId: state.currentSessionId,
      }),
    }
  )
);
