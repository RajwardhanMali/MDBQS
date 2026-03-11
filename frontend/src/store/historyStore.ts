import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { HistoryItem, Message } from '../types/apiTypes';

interface LegacyHistoryStore {
  chatHistories: HistoryItem[];
  currentChatId: string | null;
  createChat: (title?: string) => string;
  saveCurrentChat: (messages: Message[], title?: string) => void;
  loadChat: (chatId: string) => HistoryItem | null;
  deleteChat: (chatId: string) => void;
  clearAllHistory: () => void;
  setCurrentChat: (chatId: string | null) => void;
  getCurrentChat: () => HistoryItem | null;
  searchChats: (query: string) => HistoryItem[];
  getRecentChats: (limit?: number) => HistoryItem[];
  getChatCount: () => number;
  exportHistory: () => string;
  importHistory: (data: string) => boolean;
}

export const useHistoryStore = create<LegacyHistoryStore>()(
  persist(
    (set, get) => ({
      chatHistories: [],
      currentChatId: null,
      createChat: (title?: string) => {
        const id = `chat-${Date.now()}`;
        const item: HistoryItem = {
          id,
          query: title ?? 'New Chat',
          timestamp: Date.now(),
        };
        set((state) => ({ chatHistories: [item, ...state.chatHistories], currentChatId: id }));
        return id;
      },
      saveCurrentChat: (_messages: Message[], _title?: string) => {},
      loadChat: (chatId: string) => get().chatHistories.find((chat) => chat.id === chatId) ?? null,
      deleteChat: (chatId: string) => set((state) => ({ chatHistories: state.chatHistories.filter((c) => c.id !== chatId) })),
      clearAllHistory: () => set({ chatHistories: [], currentChatId: null }),
      setCurrentChat: (chatId: string | null) => set({ currentChatId: chatId }),
      getCurrentChat: () => {
        const { currentChatId, chatHistories } = get();
        return chatHistories.find((chat) => chat.id === currentChatId) ?? null;
      },
      searchChats: (query: string) => get().chatHistories.filter((chat) => chat.query.toLowerCase().includes(query.toLowerCase())),
      getRecentChats: (limit = 10) => get().chatHistories.slice(0, limit),
      getChatCount: () => get().chatHistories.length,
      exportHistory: () => JSON.stringify(get().chatHistories),
      importHistory: (data: string) => {
        try {
          const parsed = JSON.parse(data) as HistoryItem[];
          if (!Array.isArray(parsed)) return false;
          set({ chatHistories: parsed });
          return true;
        } catch {
          return false;
        }
      },
    }),
    {
      name: 'legacy-history-store',
      storage: createJSONStorage(() => localStorage),
    }
  )
);
