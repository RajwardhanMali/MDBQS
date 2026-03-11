import { Menu } from 'lucide-react';
import { useUIStore } from '../store/uiStore';

const TopNavbar = () => {
  const sidebarOpen = useUIStore((state) => state.sidebarOpen);
  const setSidebarOpen = useUIStore((state) => state.setSidebarOpen);

  return (
    <nav className="sticky top-0 z-40 flex h-16 items-center justify-between border-b bg-card/90 px-4 backdrop-blur">
      <div className="flex items-center gap-3">
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="rounded-md p-2 hover:bg-accent"
          aria-label="Toggle sidebar"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-base font-semibold md:text-lg">Multi-Database AI Query Engine</h1>
          <p className="hidden text-xs text-muted-foreground md:block">
            Query SQL, MongoDB, Graph, and Vector databases with natural language
          </p>
        </div>
      </div>
    </nav>
  );
};

export default TopNavbar;
