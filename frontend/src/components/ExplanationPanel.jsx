import { AlertTriangle } from "lucide-react";
export default function ExplanationPanel({ reasons }) {
  if (!reasons || reasons.length === 0) return <div className="text-sm text-slate-500">No explanations available.</div>;
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center gap-2">
        <AlertTriangle size={14} className="text-amber-400" />
        <span className="text-sm font-semibold">Why flagged?</span>
        <span className="text-xs text-slate-500">Source: risk engine (ML+Rules+Graph)</span>
      </div>
      <ul className="divide-y divide-slate-800">
        {reasons.map((r, i) => (
          <li key={i} className="px-4 py-2.5 text-sm leading-relaxed flex gap-2">
            <span className="text-amber-400 mt-1">•</span><span>{r}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
