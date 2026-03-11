import { Referral } from '../types/apiTypes';
import GraphPlaceholder from './GraphPlaceholder';

interface ReferralsTableProps {
  data: Referral[];
}

const ReferralsTable = ({ data }: ReferralsTableProps) => {
  if (!data.length) {
    return null;
  }

  return (
    <div className="space-y-3 rounded-xl border bg-card/70 p-4">
      <h3 className="text-sm font-semibold">Referrals</h3>
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-3 py-2 text-left">id</th>
              <th className="px-3 py-2 text-left">name</th>
              <th className="px-3 py-2 text-left">email</th>
              <th className="px-3 py-2 text-left">relationship</th>
            </tr>
          </thead>
          <tbody>
            {data.map((referral, index) => (
              <tr key={`${referral.id ?? index}`} className="border-t">
                <td className="px-3 py-2 font-mono text-xs">{String(referral.id ?? '-')}</td>
                <td className="px-3 py-2">{String(referral.name ?? '-')}</td>
                <td className="px-3 py-2">{String(referral.email ?? '-')}</td>
                <td className="px-3 py-2">{String(referral.relationship ?? '-')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <GraphPlaceholder />
    </div>
  );
};

export default ReferralsTable;
