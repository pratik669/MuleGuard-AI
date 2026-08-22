import { fmtCurrency } from "../utils/format.js";
export default function TransactionTable({ data, selectedId }) {
  if (!data || data.length === 0) return <div className="text-sm text-slate-500 p-4">No transactions found for this account.</div>;
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full text-sm">
        <thead className="bg-slate-900 text-slate-400 text-xs uppercase tracking-widest">
          <tr>
            <th className="px-3 py-2 text-left">Time</th>
            <th className="px-3 py-2 text-left">Direction</th>
            <th className="px-3 py-2 text-left">Counterparty</th>
            <th className="px-3 py-2 text-right">Amount</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800 bg-slate-950/50">
          {data.map(tx => {
            const isOut = tx.from_account === selectedId;
            return (
              <tr key={tx.id}>
                <td className="px-3 py-2 text-xs text-slate-400">{new Date(tx.timestamp).toLocaleString()}</td>
                <td className="px-3 py-2"><span className={`px-2 py-0.5 rounded-full text-xs border ${isOut ? "border-orange-900/50 bg-orange-950/30 text-orange-300" : "border-emerald-900/50 bg-emerald-950/30 text-emerald-300"}`}>{isOut ? "Outgoing" : "Incoming"}</span></td>
                <td className="px-3 py-2 font-mono">{isOut ? tx.to_account : tx.from_account}</td>
                <td className="px-3 py-2 text-right font-medium">{fmtCurrency(tx.amount)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
