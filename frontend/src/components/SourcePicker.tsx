import { useState } from 'react';
import { BadgeCheck, CircleAlert, Loader2, PlugZap } from 'lucide-react';
import { useChatStore } from '../store/chatStore';

const SourcePicker = () => {
  const currentSessionId = useChatStore((state) => state.currentSessionId);
  const sessions = useChatStore((state) => state.sessions);
  const sources = useChatStore((state) => state.sources);
  const sourceDetails = useChatStore((state) => state.sourceDetails);
  const sourcesLoading = useChatStore((state) => state.sourcesLoading);
  const toggleSource = useChatStore((state) => state.toggleSource);
  const fetchSourceDetails = useChatStore((state) => state.fetchSourceDetails);

  const [expandedId, setExpandedId] = useState<string | null>(null);

  const currentSession = sessions.find((session) => session.session_id === currentSessionId);

  return (
    <section className="rounded-3xl border border-border/70 bg-card/80 p-4 shadow-sm">
      <div className="mb-4 flex items-center gap-2 text-sm font-medium text-foreground">
        <PlugZap className="h-4 w-4 text-primary" />
        Source selector
      </div>

      {sourcesLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading sources
        </div>
      ) : (
        <div className="space-y-3">
          {sources.map((source) => {
            const active = currentSession?.active_server_ids.includes(source.server_id) ?? false;
            const detail = sourceDetails[source.server_id];
            const healthy = source.health === 'ok';

            return (
              <article key={source.server_id} className="rounded-2xl border border-border/70 bg-background/70 p-3">
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4 rounded border-border text-primary focus:ring-primary"
                    checked={active}
                    onChange={() => toggleSource(source.server_id)}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-medium text-foreground">{source.server_id}</p>
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] ${
                          healthy
                            ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                            : 'bg-amber-500/10 text-amber-700 dark:text-amber-300'
                        }`}
                      >
                        {healthy ? <BadgeCheck className="h-3 w-3" /> : <CircleAlert className="h-3 w-3" />}
                        {source.health}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{source.transport} transport</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {source.capabilities.map((capability) => (
                        <span key={capability} className="rounded-full border border-border/70 px-2 py-0.5 text-[11px] text-muted-foreground">
                          {capability}
                        </span>
                      ))}
                    </div>
                    <button
                      type="button"
                      className="mt-3 text-xs font-medium text-primary"
                      onClick={() => {
                        const next = expandedId === source.server_id ? null : source.server_id;
                        setExpandedId(next);
                        if (next) {
                          void fetchSourceDetails(source.server_id);
                        }
                      }}
                    >
                      {expandedId === source.server_id ? 'Hide details' : 'Show details'}
                    </button>
                    {expandedId === source.server_id && (
                      <div className="mt-3 rounded-2xl bg-muted/50 p-3 text-xs text-muted-foreground">
                        <p className="font-medium text-foreground">Tools</p>
                        <ul className="mt-2 space-y-1">
                          {(detail?.tools ?? source.tools).map((tool) => (
                            <li key={tool.name}>{tool.name}{tool.description ? `: ${tool.description}` : ''}</li>
                          ))}
                        </ul>
                        <p className="mt-3 font-medium text-foreground">Resources</p>
                        <ul className="mt-2 space-y-1">
                          {(detail?.resources ?? source.resources).map((resource) => (
                            <li key={resource.uri}>{resource.name} ({resource.mime_type})</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
};

export default SourcePicker;
