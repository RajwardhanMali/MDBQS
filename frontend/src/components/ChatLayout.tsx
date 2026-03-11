import { useEffect } from 'react';
import { useUIStore } from '../store/uiStore';
import Sidebar from './Sidebar';
import TopNavbar from './TopNavbar';
import ChatWindow from './ChatWindow';

const ChatLayout = () => {
  const sidebarOpen = useUIStore((state) => state.sidebarOpen);
  const setSidebarOpen = useUIStore((state) => state.setSidebarOpen);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && window.innerWidth < 1024) {
        setSidebarOpen(false);
      }

      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        const input = document.querySelector('textarea[data-query-input="true"]') as HTMLTextAreaElement | null;
        input?.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [setSidebarOpen]);

  return (
    <div className="h-screen overflow-hidden bg-background text-foreground">
      <TopNavbar />
      <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
        <Sidebar />
        <main className={`min-w-0 flex-1 transition-all duration-300 ${sidebarOpen ? 'lg:ml-80' : ''}`}>
          <ChatWindow />
        </main>
      </div>

      {sidebarOpen && (
        <button
          className="fixed inset-0 z-40 bg-ink/20 lg:hidden"
          aria-label="Close sidebar"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  );
};

export default ChatLayout;
