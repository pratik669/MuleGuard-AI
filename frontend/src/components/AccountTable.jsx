import { useNavigate } from "react-router-dom";
import RiskBadge from "./RiskBadge.jsx";
import { fmtScore } from "../utils/format.js";

export default function AccountTable({ data }) {
  const nav = useNavigate();
  if (!data || data.length === 0) return <div className="text-sm text-slate-500 p-6">No accounts found.</div>;
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full text-sm">
        <thead className="bg-slate-900 text-slate-400 text-xs uppercase tracking-widest">
          <tr>
            <th className="px-3 py-2 text-left">Account</th>
            <th className="px-3 py-2 text-left">Risk</th>
            <th className="px-3 py-2 text-right">Final</th>
            <th className="px-3 py-2 text-right">ML</th>
            <th className="px-3 py-2 text-right">Rules</th>
            <th className="px-3 py-2 text-right">Graph</th>
            <th className="px-3 py-2 text-left">Primary reason</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800 bg-slate-950/50">
          {data.map(r => (
            <tr key={r.account_id} onClick={() => nav(`/accounts/${r.account_id}`)} className="hover:bg-slate-900 cursor-pointer">
              <td className="px-3 py-2 font-mono font-medium">{r.account_id}</td>
              <td className="px-3 py-2"><RiskBadge level={r.risk_level} /></td>
              <td className="px-3 py-2 text-right font-semibold">{fmtScore(r.final_score)}</td>
              <td className="px-3 py-2 text-right text-slate-400">{fmtScore(r.ml_score)}</td>
              <td className="px-3 py-2 text-right text-slate-400">{fmtScore(r.rule_score)}</td>
              <td className="px-3 py-2 text-right text-slate-400">{fmtScore(r.graph_score)}</td>
              <td className="px-3 py-2 max-w-[360px] truncate text-slate-300">{r.reasons?.[0] || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
