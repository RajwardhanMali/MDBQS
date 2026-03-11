import { useMemo, useState } from 'react';
import { Loader2, Search } from 'lucide-react';
import { useChatStore } from '../store/chatStore';

const SchemaSearchPanel = () => {
  const [query, setQuery] = useState('');
  const searchSchema = useChatStore((state) => state.searchSchema);
  const schemaSuggestions = useChatStore((state) => state.schemaSuggestions);
  const schemaLoading = useChatStore((state) => state.schemaLoading);
  const setComposerDraft = useChatStore((state) => state.setComposerDraft);

  const debouncedSearch = useMemo(() => {
    let timeout: ReturnType<typeof setTimeout> | undefined;
    return (value: string) => {
      if (timeout) {
        clearTimeout(timeout);
      }

      timeout = setTimeout(() => {
        void searchSchema(value);
      }, 250);
    };
  }, [searchSchema]);

  return (
    <section className="rounded-3xl border border-border/70 bg-card/80 p-4 shadow-sm">
      <div className="mb-4 flex items-center gap-2 text-sm font-medium text-foreground">
        <Search className="h-4 w-4 text-primary" />
        Schema search
      </div>

      <div className="relative">
        <input
          value={query}
          onChange={(event) => {
            const next = event.target.value;
            setQuery(next);
            debouncedSearch(next);
          }}
          placeholder="Search fields, entities, or sources"
          className="w-full rounded-2xl border border-border/70 bg-background/80 px-4 py-2.5 pr-10 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        {schemaLoading && <Loader2 className="absolute right-3 top-3 h-4 w-4 animate-spin text-muted-foreground" />}
      </div>

      <div className="mt-4 space-y-3">
        {schemaSuggestions.length === 0 ? (
          <p className="text-sm text-muted-foreground">Search the schema to discover what entities and fields are available.</p>
        ) : (
          schemaSuggestions.map((hit) => (
            <button
              key={hit.id}
              type="button"
              onClick={() => setComposerDraft(hit.text)}
              className="block w-full rounded-2xl border border-border/70 bg-background/70 p-3 text-left transition-colors hover:bg-accent"
            >
              <p className="text-sm font-medium text-foreground">{hit.text}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {[hit.source, hit.entity, hit.field, hit.field_type].filter(Boolean).join(' | ')}
              </p>
            </button>
          ))
        )}
      </div>
    </section>
  );
};

export default SchemaSearchPanel;

