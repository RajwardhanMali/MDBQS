import { History, MessageSquarePlus, Moon, Sun, Trash2, X } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { useUIStore } from '../store/uiStore';
import { formatDateTime, truncateString } from '../utils/formatters';

const Sidebar = () => {
  const sidebarOpen = useUIStore((state) => state.sidebarOpen);
  const setSidebarOpen = useUIStore((state) => state.setSidebarOpen);
  const theme = useUIStore((state) => state.theme);
  const toggleTheme = useUIStore((state) => state.toggleTheme);

  const history = useChatStore((state) => state.history);
  const clearChat = useChatStore((state) => state.clearChat);
  const loadHistoryItem = useChatStore((state) => state.loadHistoryItem);
  const deleteHistoryItem = useChatStore((state) => state.deleteHistoryItem);

  return (
    <aside
      className={`fixed left-0 top-16 z-50 h-[calc(100vh-4rem)] w-80 border-r bg-card/95 backdrop-blur transition-transform duration-300 ${
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      }`}
    >
      <div className="flex h-full flex-col">
        <div className="border-b p-4">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">MDBQS Chat</h2>
            <button className="rounded p-1 hover:bg-accent md:hidden" onClick={() => setSidebarOpen(false)}>
              <X className="h-4 w-4" />
            </button>
          </div>
          <button
            onClick={clearChat}
            className="flex w-full items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground"
          >
            <MessageSquarePlus className="h-4 w-4" />
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <History className="h-4 w-4" />
            Query history
          </div>

          {history.length === 0 ? (
            <p className="text-sm text-muted-foreground">No queries yet.</p>
          ) : (
            <div className="space-y-2">
              {history.map((item) => (
                <div key={item.id} className="group flex items-start gap-2 rounded-lg border p-2 hover:bg-accent">
                  <button
                    onClick={() => {
                      loadHistoryItem(item.id);
                      if (window.innerWidth < 768) {
                        setSidebarOpen(false);
                      }
                    }}
                    className="flex-1 p-1 text-left"
                  >
                    <p className="text-sm font-medium">{truncateString(item.query, 56)}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{formatDateTime(item.timestamp)}</p>
                  </button>
                  <button
                    type="button"
                    aria-label="Delete chat"
                    className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive md:opacity-0 md:group-hover:opacity-100"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteHistoryItem(item.id);
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="border-t p-4">
          <button onClick={toggleTheme} className="flex items-center gap-2 rounded-lg px-2 py-1 text-sm hover:bg-accent">
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </button>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;

