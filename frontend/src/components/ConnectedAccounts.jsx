import { useNavigate } from "react-router-dom";
import { fmtCurrency } from "../utils/format.js";
export default function ConnectedAccounts({ data }) {
  const nav = useNavigate();
  if (!data || data.length === 0) return <div className="text-sm text-slate-500 p-4">No connected accounts found.</div>;
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full text-sm">
        <thead className="bg-slate-900 text-slate-400 text-xs uppercase tracking-widest">
          <tr>
            <th className="px-3 py-2 text-left">Counterparty</th>
            <th className="px-3 py-2 text-left">Dir</th>
            <th className="px-3 py-2 text-right">Tx</th>
            <th className="px-3 py-2 text-right">Total</th>
            <th className="px-3 py-2 text-left">First / Last</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800 bg-slate-950/50">
          {data.map(c => (
            <tr key={`${c.account_id}-${c.direction}`} onClick={() => nav(`/accounts/${c.account_id}`)} className="hover:bg-slate-900 cursor-pointer">
              <td className="px-3 py-2 font-mono">{c.account_id}</td>
              <td className="px-3 py-2"><span className={`text-xs px-2 py-0.5 rounded-full border ${c.direction==="incoming" ? "border-emerald-900/50 text-emerald-300" : "border-orange-900/50 text-orange-300"}`}>{c.direction}</span></td>
              <td className="px-3 py-2 text-right">{c.transaction_count}</td>
              <td className="px-3 py-2 text-right">{fmtCurrency(c.total_amount)}</td>
              <td className="px-3 py-2 text-xs text-slate-400">{new Date(c.first_seen).toLocaleDateString()} → {new Date(c.last_seen).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
