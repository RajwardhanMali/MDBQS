import { useMemo, useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Customer } from '../types/apiTypes';

interface CustomersTableProps {
  customers: Customer[];
}

type SortKey = 'id' | 'name' | 'email';

const PAGE_SIZE = 5;

export function CustomersTable({ customers }: CustomersTableProps) {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [desc, setDesc] = useState(false);

  const rows = useMemo(() => {
    const normalized = customers.map((c) => ({
      ...c,
      id: c.id ?? c.customer_id ?? '',
      name: c.name ?? '',
      email: c.email ?? '',
    }));

    const filtered = normalized.filter(
      (c) =>
        c.id.toLowerCase().includes(search.toLowerCase()) ||
        c.name.toLowerCase().includes(search.toLowerCase()) ||
        c.email.toLowerCase().includes(search.toLowerCase())
    );

    const sorted = filtered.sort((a, b) => a[sortKey].localeCompare(b[sortKey]));
    return desc ? sorted.reverse() : sorted;
  }, [customers, search, sortKey, desc]);

  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const pageRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const onSort = (key: SortKey) => {
    if (key === sortKey) {
      setDesc((prev) => !prev);
      return;
    }
    setSortKey(key);
    setDesc(false);
  };

  const icon = (key: SortKey) => (key !== sortKey ? null : desc ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />);

  return (
    <div className="space-y-3 rounded-xl border bg-card/70 p-4">
      <h3 className="text-sm font-semibold">Customers</h3>
      <input
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          setPage(1);
        }}
        placeholder="Search customers"
        className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
      />

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="cursor-pointer px-3 py-2 text-left" onClick={() => onSort('id')}>
                <span className="inline-flex items-center gap-1">id {icon('id')}</span>
              </th>
              <th className="cursor-pointer px-3 py-2 text-left" onClick={() => onSort('name')}>
                <span className="inline-flex items-center gap-1">name {icon('name')}</span>
              </th>
              <th className="cursor-pointer px-3 py-2 text-left" onClick={() => onSort('email')}>
                <span className="inline-flex items-center gap-1">email {icon('email')}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((customer, index) => (
              <tr key={`${customer.id}-${index}`} className="border-t">
                <td className="px-3 py-2 font-mono text-xs">{customer.id || '-'}</td>
                <td className="px-3 py-2">{customer.name || '-'}</td>
                <td className="px-3 py-2">{customer.email || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {rows.length > PAGE_SIZE && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            Page {page} of {totalPages}
          </span>
          <div className="space-x-2">
            <button disabled={page <= 1} className="rounded border px-2 py-1 disabled:opacity-40" onClick={() => setPage((p) => Math.max(1, p - 1))}>
              Prev
            </button>
            <button
              disabled={page >= totalPages}
              className="rounded border px-2 py-1 disabled:opacity-40"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
