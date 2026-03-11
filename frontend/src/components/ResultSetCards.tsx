import { formatValue, humanizeKey } from '../utils/formatters';

interface ResultSetCardsProps {
  items: Record<string, unknown>[];
}

const ResultSetCards = ({ items }: ResultSetCardsProps) => {
  return (
    <div className="grid gap-3">
      {items.map((item, index) => (
        <article key={`card-${index}`} className="rounded-2xl border border-border/70 bg-background/70 p-4">
          <div className="grid gap-3 md:grid-cols-2">
            {Object.entries(item).map(([key, value]) => {
              const nested = value && typeof value === 'object';
              return (
                <div key={key} className="min-w-0">
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{humanizeKey(key)}</p>
                  {nested ? (
                    <pre className="mt-2 overflow-x-auto rounded-xl bg-muted/60 p-3 text-xs text-muted-foreground">
                      {JSON.stringify(value, null, 2)}
                    </pre>
                  ) : (
                    <p className="mt-1 break-words text-sm text-foreground">{formatValue(value)}</p>
                  )}
                </div>
              );
            })}
          </div>
        </article>
      ))}
    </div>
  );
};

export default ResultSetCards;
