export function FeatureGroup({ title, children }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900">
      <div className="px-3 py-2 border-b border-slate-800 text-xs font-semibold uppercase tracking-widest text-slate-400">{title}</div>
      <div className="p-3 grid grid-cols-2 gap-3">{children}</div>
    </div>
  );
}
export function FeatureItem({ label, value, sub }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-sm font-medium text-slate-100">{value}</div>
      {sub && <div className="text-xs text-slate-500">{sub}</div>}
    </div>
  );
}
