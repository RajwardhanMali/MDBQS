import { useMemo } from 'react';
import { QueryResponse } from '../types/apiTypes';
import CustomerCard from './CustomerCard';
import { CustomersTable } from './CustomersTable';
import { OrdersTable } from './OrdersTable';
import { OrdersChart } from './OrdersChart';
import ReferralsTable from './ReferralsTable';
import SimilarCustomersList from './SimilarCustomersList';
import ExplainChips from './ExplainChips';
import ProvenanceDrawer from './ProvenanceDrawer';

interface AssistantResponseProps {
  result: QueryResponse;
}

const AssistantResponse = ({ result }: AssistantResponseProps) => {
  const fused = result.fused_data ?? {};

  const explain = useMemo(
    () => fused.explain ?? result.explain ?? [],
    [fused.explain, result.explain]
  );

  const customer =
    fused.customer &&
    (Boolean(fused.customer.id) ||
      Boolean(fused.customer.customer_id) ||
      Boolean(fused.customer.name) ||
      Boolean(fused.customer.email))
      ? fused.customer
      : undefined;
  const customers = fused.customers ?? [];
  const recentOrders = fused.recent_orders ?? [];
  const referrals = fused.referrals ?? [];
  const similar = fused.similar_customers ?? [];

  const hasAnyData = Boolean(customer) || customers.length > 0 || recentOrders.length > 0 || referrals.length > 0 || similar.length > 0;

  return (
    <div className="mt-3 space-y-4">
      {customer && <CustomerCard customer={customer} />}

      {customers.length > 0 && <CustomersTable customers={customers} />}

      {recentOrders.length > 0 && (
        <div className="space-y-3 rounded-xl border bg-card/70 p-4">
          <h3 className="text-sm font-semibold">Recent Orders</h3>
          <OrdersTable orders={recentOrders} />
          <OrdersChart orders={recentOrders} />
        </div>
      )}

      {referrals.length > 0 && <ReferralsTable data={referrals} />}

      {similar.length > 0 && <SimilarCustomersList customers={similar} />}

      {explain.length > 0 && <ExplainChips chips={explain} />}

      <ProvenanceDrawer data={fused.provenance} />

      {!hasAnyData && <div className="rounded-xl border bg-card/60 p-4 text-sm text-muted-foreground">No results found for this query.</div>}
    </div>
  );
};

export default AssistantResponse;
