import { formatValue, humanizeKey } from '../utils/formatters';

interface ResultSetTableProps {
  items: Record<string, unknown>[];
  keys: string[];
}

const ResultSetTable = ({ items, keys }: ResultSetTableProps) => {
  return (
    <div className="overflow-hidden rounded-2xl border border-border/70">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-border/70 text-sm">
          <thead className="bg-muted/60 text-left text-xs uppercase tracking-[0.16em] text-muted-foreground">
            <tr>
              {keys.map((key) => (
                <th key={key} className="px-4 py-3 font-medium">
                  {humanizeKey(key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border/70 bg-background/70">
            {items.map((item, rowIndex) => (
              <tr key={`row-${rowIndex}`}>
                {keys.map((key) => {
                  const value = item[key];
                  const nested = value && typeof value === 'object';
                  return (
                    <td key={`${rowIndex}-${key}`} className="max-w-[18rem] px-4 py-3 align-top text-foreground">
                      {nested ? (
                        <details>
                          <summary className="cursor-pointer text-muted-foreground">Expand</summary>
                          <pre className="mt-2 overflow-x-auto rounded-xl bg-muted/60 p-2 text-xs text-muted-foreground">
                            {JSON.stringify(value, null, 2)}
                          </pre>
                        </details>
                      ) : (
                        <span className="break-words">{formatValue(value)}</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ResultSetTable;
