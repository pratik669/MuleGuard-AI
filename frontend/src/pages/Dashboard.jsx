import { useEffect, useState } from "react";
import { getStats } from "../api/stats.js";
import AccountTable from "../components/AccountTable.jsx";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";

const COLORS = { LOW: "#475569", MEDIUM: "#f59e0b", HIGH: "#f97316", CRITICAL: "#ef4444" };

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await getStats();
        if (!cancelled) setData(res.data);
      } catch (e) {
        if (!cancelled) setErr(e.status === 0 || e.message === "Failed to fetch" ? "Unable to connect to MuleGuard API. Is the backend running on http://localhost:4000?" : e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (loading) return <div className="p-6 text-sm text-slate-400">Loading dashboard…</div>;
  if (err) return <div className="p-6"><div className="text-sm text-red-400">Unable to load dashboard: {err}</div><div className="text-xs text-slate-500 mt-1">Check that backend is running and DATABASE_URL is correct.</div></div>;

  const pie = Object.entries(data.risk_distribution).map(([name, value]) => ({ name, value }));
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Investigation Overview</h1>
        <p className="text-sm text-slate-400">Real-time risk from pipeline (425 accounts). Anomaly ≠ fraud.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4"><div className="text-xs uppercase tracking-widest text-slate-400">Total</div><div className="text-2xl font-bold">{data.total_accounts}</div></div>
        {["CRITICAL","HIGH","MEDIUM","LOW"].map(lvl => (
          <div key={lvl} className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <div className="text-xs uppercase tracking-widest text-slate-400">{lvl}</div>
            <div className="text-2xl font-bold">{data.risk_distribution[lvl]}</div>
            <div className="text-xs mt-1" style={{color: COLORS[lvl]}}>{lvl}</div>
          </div>
        ))}
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        <div className="md:col-span-2 rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div className="text-sm font-semibold mb-2">Top Risk Accounts</div>
          <AccountTable data={data.top_risk_accounts} />
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div className="text-sm font-semibold mb-2">Risk Distribution</div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pie} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={2}>
                  {pie.map(e => <Cell key={e.name} fill={COLORS[e.name]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="text-xs text-slate-500 mt-2">Source: risk_scores (ML 40% + Rules 30% + Graph 30%)</div>
        </div>
      </div>
    </div>
  );
}
