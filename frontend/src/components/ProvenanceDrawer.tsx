import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface ProvenanceDrawerProps {
  data?: Record<string, unknown>;
}

const ProvenanceDrawer = ({ data }: ProvenanceDrawerProps) => {
  const [open, setOpen] = useState(false);

  if (!data || Object.keys(data).length === 0) {
    return null;
  }

  return (
    <div className="rounded-xl border bg-card/60">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-sm font-medium">Sources Used</span>
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>
      {open && (
        <pre className="max-h-72 overflow-auto border-t bg-muted/40 p-4 text-xs">{JSON.stringify(data, null, 2)}</pre>
      )}
    </div>
  );
};

export default ProvenanceDrawer;
