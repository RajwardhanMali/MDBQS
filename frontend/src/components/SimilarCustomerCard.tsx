import { SimilarCustomer } from '../types/apiTypes';

interface SimilarCustomerCardProps {
  customer: SimilarCustomer;
  rank: number;
}

const SimilarCustomerCard = ({ customer, rank }: SimilarCustomerCardProps) => {
  const name = customer.metadata?.name ?? 'Unknown';
  const email = customer.metadata?.email ?? 'No email';

  return (
    <div className="rounded-lg border bg-background/60 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">#{rank}</span>
        <span className="text-xs text-muted-foreground">distance: {Number(customer.distance ?? 0).toFixed(3)}</span>
      </div>
      <p className="text-sm font-medium">{name}</p>
      <p className="text-xs text-muted-foreground">{email}</p>
      <p className="mt-2 text-xs">score: {Number(customer.score ?? 0).toFixed(3)}</p>
    </div>
  );
};

export default SimilarCustomerCard;
