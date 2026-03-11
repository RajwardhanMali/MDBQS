import { SimilarCustomer } from '../types/apiTypes';
import SimilarCustomerCard from './SimilarCustomerCard';

interface SimilarCustomersListProps {
  customers: SimilarCustomer[];
}

const SimilarCustomersList = ({ customers }: SimilarCustomersListProps) => {
  if (!customers.length) {
    return null;
  }

  return (
    <div className="space-y-3 rounded-xl border bg-card/70 p-4">
      <h3 className="text-sm font-semibold">Similar Customers</h3>
      <div className="grid gap-3 md:grid-cols-2">
        {customers.map((customer, index) => (
          <SimilarCustomerCard key={index} customer={customer} rank={index + 1} />
        ))}
      </div>
    </div>
  );
};

export default SimilarCustomersList;
