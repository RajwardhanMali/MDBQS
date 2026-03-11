import { useMemo } from 'react';
import { History, MessageSquarePlus, Moon, RadioTower, Sun, X } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { useUIStore } from '../store/uiStore';
import { formatRelativeTime, truncateString } from '../utils/formatters';

const Sidebar = () => {
  const sidebarOpen = useUIStore((state) => state.sidebarOpen);
  const setSidebarOpen = useUIStore((state) => state.setSidebarOpen);
  const theme = useUIStore((state) => state.theme);
  const toggleTheme = useUIStore((state) => state.toggleTheme);

  const sessions = useChatStore((state) => state.sessions);
  const currentSessionId = useChatStore((state) => state.currentSessionId);
  const sources = useChatStore((state) => state.sources);
  const createSession = useChatStore((state) => state.createSession);
  const selectSession = useChatStore((state) => state.selectSession);

  const currentSession = useMemo(
    () => sessions.find((session) => session.session_id === currentSessionId) ?? null,
    [currentSessionId, sessions]
  );

  return (
    <aside
      className={`fixed left-0 top-16 z-50 flex h-[calc(100vh-4rem)] w-80 flex-col border-r border-border/70 bg-card/95 backdrop-blur transition-transform duration-300 ${
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      }`}
    >
      <div className="border-b border-border/70 p-4">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="font-serif text-xl text-foreground">Sessions</h2>
            <p className="text-xs text-muted-foreground">Replayable chat over connected data sources</p>
          </div>
          <button className="rounded p-1 hover:bg-accent lg:hidden" onClick={() => setSidebarOpen(false)}>
            <X className="h-4 w-4" />
          </button>
        </div>
        <button
          onClick={() => void createSession()}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-3 py-2.5 text-sm font-medium text-primary-foreground shadow-sm"
        >
          <MessageSquarePlus className="h-4 w-4" />
          New chat
        </button>
      </div>

      <div className="border-b border-border/70 p-4">
        <div className="rounded-2xl border border-border/70 bg-muted/40 p-3">
          <div className="flex items-center gap-2 text-sm font-medium text-foreground">
            <RadioTower className="h-4 w-4 text-primary" />
            Connected sources
          </div>
          <p className="mt-2 text-2xl font-semibold text-foreground">{sources.length}</p>
          <p className="text-xs text-muted-foreground">
            {currentSession?.active_server_ids.length ?? 0} active in this session
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="mb-3 flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <History className="h-4 w-4" />
          Recent sessions
        </div>

        {sessions.length === 0 ? (
          <p className="text-sm text-muted-foreground">No saved sessions yet.</p>
        ) : (
          <div className="space-y-2">
            {sessions.map((session) => {
              const active = session.session_id === currentSessionId;

              return (
                <button
                  key={session.session_id}
                  onClick={() => {
                    void selectSession(session.session_id);
                    if (window.innerWidth < 1024) {
                      setSidebarOpen(false);
                    }
                  }}
                  className={`w-full rounded-2xl border p-3 text-left transition-colors ${
                    active
                      ? 'border-primary/40 bg-primary/10'
                      : 'border-border/70 bg-background/70 hover:bg-accent'
                  }`}
                >
                  <p className="text-sm font-medium text-foreground">
                    {truncateString(session.title || 'Untitled session', 44)}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {session.active_server_ids.length} sources | {formatRelativeTime(session.updated_at)}
                  </p>
                  {session.summary && (
                    <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">{session.summary}</p>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="border-t border-border/70 p-4">
        <button onClick={toggleTheme} className="flex items-center gap-2 rounded-lg px-2 py-1 text-sm hover:bg-accent">
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          {theme === 'dark' ? 'Light mode' : 'Dark mode'}
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;

