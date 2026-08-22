import { riskColor } from "../utils/format.js";
export default function RiskGauge({ score, level }) {
  const pct = Math.max(0, Math.min(100, Number(score) || 0));
  const color = level === "CRITICAL" ? "bg-red-500" : level === "HIGH" ? "bg-orange-500" : level === "MEDIUM" ? "bg-amber-400" : "bg-slate-500";
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs uppercase tracking-widest text-slate-400">Final Risk</span>
        <span className={`text-xs px-2 py-0.5 rounded-full border ${riskColor(level)}`}>{level}</span>
      </div>
      <div className="text-3xl font-bold tracking-tight">{pct.toFixed(1)} <span className="text-sm font-normal text-slate-400">/ 100</span></div>
      <div className="mt-3 h-2 rounded-full bg-slate-800 overflow-hidden">
        <div className={`h-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-slate-500"><span>0</span><span>100</span></div>
    </div>
  );
}
