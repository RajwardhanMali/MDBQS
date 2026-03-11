import { UserRound } from 'lucide-react';
import { Customer } from '../types/apiTypes';

interface CustomerCardProps {
  customer: Customer;
}

const CustomerCard = ({ customer }: CustomerCardProps) => {
  const id = customer.id ?? customer.customer_id ?? '-';

  return (
    <div className="rounded-xl border bg-card/70 p-4 shadow-sm backdrop-blur">
      <div className="flex items-start gap-3">
        <div className="rounded-lg bg-primary/10 p-2 text-primary">
          <UserRound className="h-5 w-5" />
        </div>
        <div>
          <h3 className="text-sm font-semibold">Customer</h3>
          <p className="text-sm">{customer.name ?? 'Unknown'}</p>
          <p className="text-xs text-muted-foreground">{customer.email ?? 'No email available'}</p>
          <p className="mt-1 text-xs text-muted-foreground">id: {id}</p>
        </div>
      </div>
    </div>
  );
};

export default CustomerCard;
