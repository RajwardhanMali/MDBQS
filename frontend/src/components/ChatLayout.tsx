import { useEffect } from 'react';
import { useUIStore } from '../store/uiStore';
import Sidebar from './Sidebar';
import TopNavbar from './TopNavbar';
import ChatWindow from './ChatWindow';

const ChatLayout = () => {
  const sidebarOpen = useUIStore((state) => state.sidebarOpen);
  const setSidebarOpen = useUIStore((state) => state.setSidebarOpen);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && window.innerWidth < 768) {
        setSidebarOpen(false);
      }

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        const input = document.querySelector('textarea[data-query-input="true"]') as HTMLTextAreaElement | null;
        input?.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [setSidebarOpen]);

  return (
    <div className="h-screen bg-background text-foreground">
      <TopNavbar />
      <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
        <Sidebar />
        <div className={`flex-1 transition-all duration-300 ${sidebarOpen ? 'md:ml-80' : ''}`}>
          <ChatWindow />
        </div>
      </div>

      {sidebarOpen && (
        <button
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          aria-label="Close sidebar"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  );
};

export default ChatLayout;
