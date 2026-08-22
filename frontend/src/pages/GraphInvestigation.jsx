import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getGraph, traceMoney } from "../api/graph.js";
import GraphView from "../components/GraphView.jsx";
import { fmtCurrency } from "../utils/format.js";

export default function GraphInvestigation() {
  const { id } = useParams();
  const [depth, setDepth] = useState(2);
  const [graph, setGraph] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [from, setFrom] = useState(id || "");
  const [to, setTo] = useState("");
  const [trace, setTrace] = useState(null);
  const [tracing, setTracing] = useState(false);

  useEffect(() => { setFrom(id); }, [id]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true); setErr(null);
      try {
        const res = await getGraph(id, depth);
        if (!cancelled) setGraph(res.data);
      } catch (e) {
        if (cancelled) return;
        const msg = e.message === "Failed to fetch" ? "Unable to connect to MuleGuard API. Is the backend running on http://localhost:4000?" : e.message;
        setErr(msg);
      } finally { if (!cancelled) setLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [id, depth]);

  const onTrace = async (e) => {
    e.preventDefault();
    setTracing(true); setTrace(null);
    try {
      const res = await traceMoney(from, to, 4);
      setTrace(res.data);
    } catch (e) { setTrace({ found: false, error: e.message }); } finally { setTracing(false); }
  };

  const highlightPath = trace?.found ? trace.path.map(p => p.account_id) : [];

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Graph Investigation</h1>
          <div className="text-sm text-slate-400">Root: <span className="font-mono text-slate-200">{id}</span> · Direction = money flow</div>
        </div>
        <Link to={`/accounts/${id}`} className="text-sm px-3 py-1.5 rounded border border-slate-800 bg-slate-900">← Account</Link>
      </div>

      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-xs text-slate-400">Depth</span>
        {[1,2,3].map(d => (
          <button key={d} onClick={() => setDepth(d)} className={`px-3 py-1 text-sm rounded border ${depth===d ? "bg-indigo-600 border-indigo-600 text-white" : "bg-slate-900 border-slate-800"}`}>{d}</button>
        ))}
        <span className="text-xs text-slate-500 ml-2">{graph ? `${graph.nodes.length} nodes · ${graph.edges.length} edges` : ""}</span>
        <div className="ml-auto flex items-center gap-2 text-xs">
          <span className="w-2 h-2 rounded-full bg-slate-500" /> LOW
          <span className="w-2 h-2 rounded-full bg-amber-400" /> MEDIUM
          <span className="w-2 h-2 rounded-full bg-orange-500" /> HIGH
          <span className="w-2 h-2 rounded-full bg-red-500" /> CRITICAL
          <span className="ml-2 text-slate-500">→ = money flow</span>
        </div>
      </div>

      {loading ? <div className="text-sm text-slate-400 p-6">Loading graph…</div> : err ? <div className="text-sm text-red-400 p-6">{err}</div> : (
        <GraphView graphData={graph} highlightPath={highlightPath} onNodeClick={(nid) => setTo(nid)} />
      )}

      <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <div className="text-sm font-semibold mb-2">Trace Money Flow</div>
        <form onSubmit={onTrace} className="flex flex-wrap gap-2 items-end">
          <div>
            <label className="text-xs text-slate-400">From</label>
            <input value={from} onChange={e=>setFrom(e.target.value)} placeholder="M0021" className="block w-32 mt-1 px-2 py-1.5 bg-slate-950 border border-slate-800 rounded text-sm font-mono" />
          </div>
          <div className="pt-5 text-slate-500">→</div>
          <div>
            <label className="text-xs text-slate-400">To (click node)</label>
            <input value={to} onChange={e=>setTo(e.target.value)} placeholder="C0139" className="block w-32 mt-1 px-2 py-1.5 bg-slate-950 border border-slate-800 rounded text-sm font-mono" />
          </div>
          <button type="submit" disabled={tracing || !from || !to} className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white rounded text-sm">Trace</button>
        </form>

        {tracing && <div className="text-xs text-slate-400 mt-3">Tracing…</div>}
        {trace && trace.found && (
          <div className="mt-4 space-y-2">
            <div className="text-sm font-medium text-emerald-300">Path found ({trace.path.length} accounts)</div>
            <div className="flex flex-wrap items-center gap-2">
              {trace.path.map((p,i) => (
                <span key={p.account_id} className="flex items-center gap-2">
                  <Link to={`/accounts/${p.account_id}`} className="px-2 py-1 rounded bg-slate-800 border border-slate-700 text-xs font-mono hover:bg-slate-700">{p.account_id}</Link>
                  {i < trace.path.length-1 && <span className="text-slate-500">↓</span>}
                </span>
              ))}
            </div>
            <div className="space-y-1">
              {trace.transactions.map(tx => (
                <div key={tx.id} className="text-xs flex gap-2 text-slate-300">
                  <span className="font-mono">{tx.from_account} → {tx.to_account}</span>
                  <span>{fmtCurrency(tx.amount)}</span>
                  <span className="text-slate-500">{new Date(tx.timestamp).toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        {trace && !trace.found && !tracing && (
          <div className="text-sm text-amber-300 mt-3">No directed money-flow path found within the selected depth.</div>
        )}
        {trace?.error && <div className="text-sm text-red-400 mt-3">{trace.error}</div>}
      </div>
    </div>
  );
}
