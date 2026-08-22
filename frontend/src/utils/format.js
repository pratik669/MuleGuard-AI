export function fmtCurrency(n) {
  if (n == null) return "-";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);
}
export function fmtNumber(n) {
  if (n == null) return "-";
  return new Intl.NumberFormat("en-IN").format(n);
}
export function fmtScore(n) {
  if (n == null) return "-";
  return Number(n).toFixed(1);
}
export function riskColor(level) {
  const map = {
    LOW: "text-slate-400 border-slate-700 bg-slate-900",
    MEDIUM: "text-amber-300 border-amber-900/50 bg-amber-950/30",
    HIGH: "text-orange-400 border-orange-900/50 bg-orange-950/30",
    CRITICAL: "text-red-400 border-red-900/50 bg-red-950/30",
  };
  return map[level] || map.LOW;
}
export function riskDot(level) {
  const map = { LOW: "bg-slate-500", MEDIUM: "bg-amber-400", HIGH: "bg-orange-500", CRITICAL: "bg-red-500" };
  return map[level] || "bg-slate-500";
}
