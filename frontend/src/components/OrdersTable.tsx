import { useMemo, useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Order } from '../types/apiTypes';
import { formatCurrency, formatDate } from '../utils/formatters';

interface OrdersTableProps {
  orders: Order[];
}

type SortKey = 'order_id' | 'customer_id' | 'amount' | 'order_date';

export function OrdersTable({ orders }: OrdersTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('order_date');
  const [desc, setDesc] = useState(true);

  const sorted = useMemo(() => {
    const next = [...orders].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];

      if (sortKey === 'amount') {
        return (Number(av) || 0) - (Number(bv) || 0);
      }

      return String(av ?? '').localeCompare(String(bv ?? ''));
    });

    return desc ? next.reverse() : next;
  }, [orders, sortKey, desc]);

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) {
      setDesc((prev) => !prev);
      return;
    }
    setSortKey(key);
    setDesc(false);
  };

  const icon = (key: SortKey) => {
    if (key !== sortKey) return null;
    return desc ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />;
  };

  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-sm">
        <thead className="bg-muted/50">
          <tr>
            <th className="cursor-pointer px-3 py-2 text-left" onClick={() => toggleSort('order_id')}>
              <span className="inline-flex items-center gap-1">order_id {icon('order_id')}</span>
            </th>
            <th className="cursor-pointer px-3 py-2 text-left" onClick={() => toggleSort('customer_id')}>
              <span className="inline-flex items-center gap-1">customer_id {icon('customer_id')}</span>
            </th>
            <th className="cursor-pointer px-3 py-2 text-left" onClick={() => toggleSort('amount')}>
              <span className="inline-flex items-center gap-1">amount {icon('amount')}</span>
            </th>
            <th className="cursor-pointer px-3 py-2 text-left" onClick={() => toggleSort('order_date')}>
              <span className="inline-flex items-center gap-1">order_date {icon('order_date')}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((order, index) => (
            <tr key={`${order.order_id ?? index}`} className="border-t">
              <td className="px-3 py-2 font-mono text-xs">{String(order.order_id ?? '-')}</td>
              <td className="px-3 py-2 font-mono text-xs">{String(order.customer_id ?? '-')}</td>
              <td className="px-3 py-2">{formatCurrency(Number(order.amount) || 0)}</td>
              <td className="px-3 py-2 text-muted-foreground">{order.order_date ? formatDate(String(order.order_date)) : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
