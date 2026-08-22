import { riskColor, riskDot } from "../utils/format.js";
export default function RiskBadge({ level, size = "sm" }) {
  const cls = riskColor(level);
  const pad = size === "lg" ? "px-3 py-1 text-sm" : "px-2 py-0.5 text-xs";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border font-semibold tracking-wide ${cls} ${pad}`}>
      <span className={`w-2 h-2 rounded-full ${riskDot(level)}`} /> {level || "UNKNOWN"}
    </span>
  );
}
