import { Menu } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { useUIStore } from '../store/uiStore';

const TopNavbar = () => {
  const sidebarOpen = useUIStore((state) => state.sidebarOpen);
  const setSidebarOpen = useUIStore((state) => state.setSidebarOpen);
  const currentSessionId = useChatStore((state) => state.currentSessionId);
  const sessions = useChatStore((state) => state.sessions);

  const currentSession = sessions.find((session) => session.session_id === currentSessionId);

  return (
    <nav className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-border/70 bg-card/90 px-4 backdrop-blur">
      <div className="flex items-center gap-3">
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="rounded-md p-2 hover:bg-accent"
          aria-label="Toggle sidebar"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div>
          <h1 className="font-serif text-lg text-foreground md:text-xl">Connected Data Chat</h1>
          <p className="hidden text-xs text-muted-foreground md:block">
            {currentSession?.title || 'Session-based workspace for querying any connected source'}
          </p>
        </div>
      </div>

      <div className="hidden rounded-full border border-border/70 bg-background/80 px-3 py-1 text-xs text-muted-foreground md:block">
        {currentSession?.active_server_ids.length ?? 0} active sources
      </div>
    </nav>
  );
};

export default TopNavbar;
