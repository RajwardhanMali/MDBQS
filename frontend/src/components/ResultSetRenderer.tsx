import { useMemo, useState } from 'react';
import { AlertTriangle, Braces, ChevronDown, ChevronUp, TableProperties } from 'lucide-react';
import { ResultSet, SimilarCustomer } from '../types/apiTypes';
import { humanizeKey } from '../utils/formatters';
import ResultSetTable from './ResultSetTable';
import ResultSetCards from './ResultSetCards';
import SimilarCustomerCard from './SimilarCustomerCard';

interface ResultSetRendererProps {
  resultSet: ResultSet;
}

const isScalar = (value: unknown) => value === null || ['string', 'number', 'boolean'].includes(typeof value);
const isPlainObject = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

const getMetaString = (meta: Record<string, unknown>, key: string) => {
  const value = meta[key];
  return typeof value === 'string' ? value : '';
};

const getMetaBoolean = (meta: Record<string, unknown>, key: string) => {
  const value = meta[key];
  return typeof value === 'boolean' ? value : undefined;
};

const mapErrorMessage = (errorCode: string) => {
  if (errorCode === 'INVALID_VECTOR_INPUT') {
    return 'Vector search could not run because the embedding input was invalid or missing.';
  }
  if (errorCode === 'MISSING_DEPENDENCY') {
    return 'This step could not run because a previous step did not return the required data.';
  }
  return 'This result set failed to execute.';
};

const flattenItem = (item: Record<string, unknown>) => {
  const flat: Record<string, unknown> = {};
  let supported = true;

  Object.entries(item).forEach(([key, value]) => {
    if (isScalar(value)) {
      flat[key] = value;
      return;
    }

    if (isPlainObject(value)) {
      const nestedEntries = Object.entries(value);
      const allScalar = nestedEntries.every(([, nestedValue]) => isScalar(nestedValue));

      if (allScalar) {
        nestedEntries.forEach(([nestedKey, nestedValue]) => {
          flat[`${key}.${nestedKey}`] = nestedValue;
        });
        return; // Bug 3 fix: missing return caused fall-through to supported=false
      }
    }

    supported = false;
  });

  return { flat, supported };
};

const ResultSetHeader = ({ resultSet, rowCount }: { resultSet: ResultSet; rowCount: number }) => (
  <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border/70 px-4 py-4">
    <div>
      <h3 className="text-base font-semibold text-foreground">{humanizeKey(resultSet.key)}</h3>
      <div className="mt-2 flex flex-wrap gap-2">
        <span className="rounded-full border border-border/70 bg-background px-3 py-1 text-xs text-muted-foreground">
          source: {resultSet.server_id}
        </span>
        <span className="rounded-full border border-border/70 bg-background px-3 py-1 text-xs text-muted-foreground">
          tool: {resultSet.tool_name}
        </span>
        <span className="rounded-full border border-border/70 bg-background px-3 py-1 text-xs text-muted-foreground">
          {rowCount} rows
        </span>
      </div>
    </div>
  </div>
);

const ResultSetErrorCard = ({
  resultSet,
  rowCount,
  error,
  errorCode,
  recoverable,
}: {
  resultSet: ResultSet;
  rowCount: number;
  error: string;
  errorCode: string;
  recoverable: boolean | undefined;
}) => {
  const sourceId = getMetaString(resultSet.meta ?? {}, 'source_id') || resultSet.server_id;

  return (
    <section className="overflow-hidden rounded-[1.75rem] border border-destructive/30 bg-card/80 shadow-sm">
      <ResultSetHeader resultSet={resultSet} rowCount={rowCount} />
      <div className="space-y-4 p-4">
        <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 flex-none text-destructive" />
            <div className="min-w-0">
              <p className="text-sm font-medium text-foreground">
                {resultSet.server_id} via {resultSet.tool_name}
              </p>
              <p className="mt-2 text-sm text-destructive">{mapErrorMessage(errorCode)}</p>
              {recoverable !== undefined && (
                <p className="mt-2 text-xs text-muted-foreground">Recoverable: {recoverable ? 'yes' : 'no'}</p>
              )}
            </div>
          </div>
        </div>

        <details className="rounded-2xl border border-border/70 bg-background/50 px-4 py-3">
          <summary className="cursor-pointer text-sm font-medium text-foreground">Technical details</summary>
          <div className="mt-3 space-y-2 text-sm text-muted-foreground">
            <p>error: {error}</p>
            <p>source_id: {sourceId}</p>
            <p>tool_name: {resultSet.tool_name}</p>
            {errorCode && <p>error_code: {errorCode}</p>}
          </div>
        </details>
      </div>
    </section>
  );
};

const EmptyResultSet = ({ resultSet, rowCount }: { resultSet: ResultSet; rowCount: number }) => (
  <section className="overflow-hidden rounded-[1.75rem] border border-border/70 bg-card/80 shadow-sm">
    <ResultSetHeader resultSet={resultSet} rowCount={rowCount} />
    <div className="p-4">
      <div className="rounded-2xl border border-dashed border-border/80 bg-background/40 px-4 py-8 text-center text-sm text-muted-foreground">
        No matching data.
      </div>
    </div>
  </section>
);

// ── Vector / similarity result set ────────────────────────────────────────────
// Detected by tool_name or key — renders using SimilarCustomerCard instead of
// the generic table so that rank, score, distance, name and email are shown.
const isVectorResultSet = (resultSet: ResultSet): boolean =>
  resultSet.tool_name === 'query.vector' || resultSet.key === 'similar_customers';

const VectorResultSet = ({ resultSet }: { resultSet: ResultSet }) => {
  const [expanded, setExpanded] = useState(false);
  const items = Array.isArray(resultSet.items) ? resultSet.items : [];
  const meta = resultSet.meta ?? {};
  const rowCount = typeof meta.row_count === 'number' ? meta.row_count : items.length;
  const visibleItems = expanded ? items : items.slice(0, 6);

  return (
    <section className="overflow-hidden rounded-[1.75rem] border border-border/70 bg-card/80 shadow-sm">
      <ResultSetHeader resultSet={resultSet} rowCount={rowCount} />
      <div className="p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {visibleItems.map((item, idx) => (
            <SimilarCustomerCard
              key={`sim-${idx}`}
              customer={item as SimilarCustomer}
              rank={idx + 1}
            />
          ))}
        </div>
        {items.length > 6 && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="mt-3 inline-flex items-center gap-2 rounded-full border border-border/70 bg-background px-3 py-1.5 text-xs text-foreground"
          >
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            {expanded ? 'Show less' : `Show all ${items.length}`}
          </button>
        )}
      </div>
    </section>
  );
};

// ── Main renderer ─────────────────────────────────────────────────────────────
const ResultSetRenderer = ({ resultSet }: ResultSetRendererProps) => {
  const [showRaw, setShowRaw] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const meta = resultSet.meta ?? {};
  const items = Array.isArray(resultSet.items) ? resultSet.items : [];
  const hasItems = items.length > 0;
  const error = getMetaString(meta, 'error');
  const errorCode = getMetaString(meta, 'error_code');
  const recoverable = getMetaBoolean(meta, 'recoverable');
  const rowCount = typeof meta.row_count === 'number' ? meta.row_count : items.length;
  const visibleItems = expanded ? items : items.slice(0, 5);

  const flattened = useMemo(() => visibleItems.map((item) => flattenItem(item)), [visibleItems]);

  const renderMode = useMemo<'table' | 'cards'>(() => {
    if (!items.length) return 'cards';
    const directlyFlat = items.every((item) => Object.values(item).every(isScalar));
    if (directlyFlat) return 'table';
    const flattenable = items.every((item) => flattenItem(item).supported);
    return flattenable ? 'table' : 'cards';
  }, [items]);

  const keys = useMemo(() => {
    const ordered = new Set<string>();
    const source = renderMode === 'table' ? flattened.map((entry) => entry.flat) : visibleItems;
    source.forEach((item) => Object.keys(item).forEach((key) => ordered.add(key)));
    return Array.from(ordered);
  }, [flattened, renderMode, visibleItems]);

  const tableItems = useMemo(() => flattened.map((entry) => entry.flat), [flattened]);

  if (error) {
    return (
      <ResultSetErrorCard
        resultSet={resultSet}
        rowCount={rowCount}
        error={error}
        errorCode={errorCode}
        recoverable={recoverable}
      />
    );
  }

  if (!hasItems) {
    return <EmptyResultSet resultSet={resultSet} rowCount={rowCount} />;
  }

  // Vector results get the dedicated card grid
  if (isVectorResultSet(resultSet)) {
    return <VectorResultSet resultSet={resultSet} />;
  }

  return (
    <section className="overflow-hidden rounded-[1.75rem] border border-border/70 bg-card/80 shadow-sm">
      <ResultSetHeader resultSet={resultSet} rowCount={rowCount} />

      <div className="space-y-4 p-4">
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setShowRaw((value) => !value)}
            className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background px-3 py-1.5 text-xs text-foreground"
          >
            <Braces className="h-3.5 w-3.5" />
            {showRaw ? 'Hide JSON' : 'Raw JSON'}
          </button>
          {items.length > 5 && (
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background px-3 py-1.5 text-xs text-foreground"
            >
              {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              {expanded ? 'Show less' : `Show all ${items.length}`}
            </button>
          )}
          {renderMode === 'table' && (
            <span className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-background px-3 py-1.5 text-xs text-muted-foreground">
              <TableProperties className="h-3.5 w-3.5" />
              {keys.length} columns
            </span>
          )}
        </div>

        {showRaw ? (
          <pre className="overflow-auto rounded-xl bg-background/70 p-4 text-xs text-foreground">
            {JSON.stringify(visibleItems, null, 2)}
          </pre>
        ) : renderMode === 'table' ? (
          <ResultSetTable keys={keys} items={tableItems} />
        ) : (
          <ResultSetCards keys={keys} items={visibleItems} />
        )}
      </div>
    </section>
  );
};

export default ResultSetRenderer;