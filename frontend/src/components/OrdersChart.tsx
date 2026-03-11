import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Order } from '../types/apiTypes';

interface OrdersChartProps {
  orders: Order[];
}

export function OrdersChart({ orders }: OrdersChartProps) {
  const data = orders.slice(0, 8).map((order, index) => ({
    label: String(order.order_id ?? `order-${index + 1}`).slice(0, 10),
    amount: Number(order.amount) || 0,
  }));

  if (!data.length) {
    return null;
  }

  return (
    <div className="h-72 w-full rounded-lg border bg-background/50 p-2">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip formatter={(value: number) => [`$${value.toFixed(2)}`, 'Amount']} />
          <Bar dataKey="amount" fill="hsl(var(--primary))" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
