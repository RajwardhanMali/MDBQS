import { useMemo } from 'react';
import { Loader2, Orbit, TriangleAlert } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { TraceShape } from '../types/apiTypes';

interface TraceViewerProps {
  messageId: string;
  initialTrace: TraceShape;
}

const TraceViewer = ({ messageId, initialTrace }: TraceViewerProps) => {
  const runTraces = useChatStore((state) => state.runTraces);
  const traceLoadingIds = useChatStore((state) => state.traceLoadingIds);
  const loadRunTrace = useChatStore((state) => state.loadRunTrace);

  const detailedTrace = runTraces[messageId];
  const loading = traceLoadingIds.includes(messageId);

  const trace = useMemo(() => {
    if (detailedTrace) {
      return {
        plan: detailedTrace.plan,
        tool_calls: detailedTrace.tool_calls,
        errors: detailedTrace.errors,
        timings: detailedTrace.timings,
      };
    }

    return initialTrace;
  }, [detailedTrace, initialTrace]);

  return (
    <details className="rounded-2xl border border-border/70 bg-card/70 p-4 shadow-sm">
      <summary className="cursor-pointer list-none">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-foreground">Trace</p>
            <p className="text-xs text-muted-foreground">Plan, tool calls, errors, and timings for this message.</p>
          </div>
          {!detailedTrace && (
            <button
              type="button"
              onClick={(event) => {
                event.preventDefault();
                void loadRunTrace(messageId);
              }}
              className="rounded-full border border-border/70 bg-background px-3 py-1 text-xs text-foreground"
            >
              {loading ? 'Loading...' : 'Load full trace'}
            </button>
          )}
        </div>
      </summary>

      <div className="mt-4 space-y-4">
        {loading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading detailed run trace
          </div>
        )}

        <section className="rounded-2xl border border-border/70 bg-background/60 p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
            <Orbit className="h-4 w-4 text-primary" />
            Plan
          </div>
          <pre className="overflow-x-auto text-xs text-muted-foreground">{JSON.stringify(trace.plan ?? [], null, 2)}</pre>
        </section>

        <section className="rounded-2xl border border-border/70 bg-background/60 p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
            <Orbit className="h-4 w-4 text-primary" />
            Tool calls
          </div>
          <pre className="overflow-x-auto text-xs text-muted-foreground">{JSON.stringify(trace.tool_calls ?? [], null, 2)}</pre>
        </section>

        <section className="rounded-2xl border border-border/70 bg-background/60 p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
            <TriangleAlert className="h-4 w-4 text-primary" />
            Errors
          </div>
          <pre className="overflow-x-auto text-xs text-muted-foreground">{JSON.stringify(trace.errors ?? [], null, 2)}</pre>
        </section>

        {'timings' in trace && trace.timings && (
          <section className="rounded-2xl border border-border/70 bg-background/60 p-3">
            <div className="mb-2 text-sm font-medium text-foreground">Timings</div>
            <pre className="overflow-x-auto text-xs text-muted-foreground">{JSON.stringify(trace.timings, null, 2)}</pre>
          </section>
        )}
      </div>
    </details>
  );
};

export default TraceViewer;
