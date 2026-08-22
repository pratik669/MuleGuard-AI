import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { getAccount, getTransactions, getConnected } from "../api/accounts.js";
import RiskBadge from "../components/RiskBadge.jsx";
import RiskGauge from "../components/RiskGauge.jsx";
import ExplanationPanel from "../components/ExplanationPanel.jsx";
import { FeatureGroup, FeatureItem } from "../components/FeatureCard.jsx";
import TransactionTable from "../components/TransactionTable.jsx";
import ConnectedAccounts from "../components/ConnectedAccounts.jsx";
import { fmtCurrency, fmtNumber } from "../utils/format.js";

export default function AccountDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [tx, setTx] = useState({ data: [], pagination: { total: 0 } });
  const [txPage, setTxPage] = useState(0);
  const [txOrder, setTxOrder] = useState("desc");
  const [connected, setConnected] = useState([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true); setErr(null);
      try {
        const [res, t, c] = await Promise.all([
          getAccount(id),
          getTransactions(id, { limit: 10, offset: 0, order: txOrder }),
          getConnected(id),
        ]);
        if (cancelled) return;
        setData(res.data);
        setTx(t);
        setConnected(c.data.connected);
      } catch (e) {
        if (cancelled) return;
        const msg = e.status === 404 ? e.message : (e.message === "Failed to fetch" ? "Unable to connect to MuleGuard API. Is the backend running on http://localhost:4000?" : e.message);
        setErr(msg);
      } finally { if (!cancelled) setLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [id]);

  const loadTx = async (off, order = txOrder) => {
    const t = await getTransactions(id, { limit: 10, offset: off, order });
    setTx(t); setTxPage(off);
  };
  const setOrderAndReload = async (newOrder) => {
    setTxOrder(newOrder);
    const t = await getTransactions(id, { limit: 10, offset: 0, order: newOrder });
    setTx(t); setTxPage(0);
  };

  if (loading) return (
    <div className="p-6 space-y-6 animate-pulse">
      <div className="h-6 bg-slate-800 rounded w-1/3" />
      <div className="grid md:grid-cols-3 gap-6">
        <div className="h-32 bg-slate-800 rounded" />
        <div className="md:col-span-2 h-32 bg-slate-800 rounded" />
      </div>
      <div className="grid md:grid-cols-3 gap-4">
        <div className="h-24 bg-slate-800 rounded" />
        <div className="h-24 bg-slate-800 rounded" />
        <div className="h-24 bg-slate-800 rounded" />
      </div>
      <div className="h-48 bg-slate-800 rounded" />
      <div className="h-32 bg-slate-800 rounded" />
      <div className="text-xs text-slate-500">Loading account {id}…</div>
    </div>
  );
  if (err) return <div className="p-6"><div className="text-sm text-red-400">Error: {err}</div><div className="text-xs text-slate-500 mt-1">Check backend at http://localhost:4000/api/health</div><button onClick={() => nav(-1)} className="mt-2 text-sm underline">Go back</button></div>;
  if (!data) return <div className="p-6 text-sm">Not found</div>;

  const { account, risk, features } = data;
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs tracking-widest uppercase text-slate-500">Account Investigation</div>
          <h1 className="text-2xl font-bold font-mono">{account.id} <span className="text-base font-normal text-slate-400">{account.name}</span></h1>
          <div className="text-xs text-slate-500">{account.type} · created {new Date(account.created_at).toLocaleDateString()}</div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <RiskBadge level={risk.risk_level} size="lg" />
          <div className="text-xs text-slate-400">{risk.final_score?.toFixed(1)} / 100</div>
          <Link to={`/graph/${account.id}`} className="text-sm px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-white">Open Graph →</Link>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        <div className="space-y-4">
          <RiskGauge score={risk.final_score} level={risk.risk_level} />
          <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 space-y-2">
            <div className="text-xs uppercase tracking-widest text-slate-400">Risk Breakdown</div>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between"><span className="text-slate-400">Anomaly (ML)</span><span className="font-medium">{risk.ml_score?.toFixed(1)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Behavioral (Rules)</span><span className="font-medium">{risk.rule_score?.toFixed(1)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Graph</span><span className="font-medium">{risk.graph_score?.toFixed(1)}</span></div>
              <div className="border-t border-slate-800 pt-2 flex justify-between font-semibold"><span>Final</span><span>{risk.final_score?.toFixed(1)}</span></div>
            </div>
            <div className="text-[11px] text-slate-500">Weights ML 40% + Rules 30% + Graph 30% (demo, not validated). Anomaly ≠ fraud.</div>
          </div>
        </div>
        <div className="md:col-span-2">
          <ExplanationPanel reasons={risk.reasons} />
        </div>
      </div>

      {features && (
        <div className="grid md:grid-cols-3 gap-4">
          <FeatureGroup title="Transaction Volume">
            <FeatureItem label="Total In" value={fmtCurrency(features.total_in)} />
            <FeatureItem label="Total Out" value={fmtCurrency(features.total_out)} />
            <FeatureItem label="Tx Count" value={fmtNumber(features.tx_count)} sub={`${features.cnt_in} in / ${features.cnt_out} out`} />
            <FeatureItem label="In/Out Ratio" value={fmtNumber(features.inflow_outflow_ratio)} />
          </FeatureGroup>
          <FeatureGroup title="Counterparties">
            <FeatureItem label="Unique Senders" value={features.unique_senders} />
            <FeatureItem label="Unique Receivers" value={features.unique_receivers} />
            <FeatureItem label="Fan-In Score" value={features.fan_in_score} />
            <FeatureItem label="Fan-Out Score" value={features.fan_out_score} />
          </FeatureGroup>
          <FeatureGroup title="Activity & Amounts">
            <FeatureItem label="Velocity" value={`${features.velocity_per_hour}/h`} />
            <FeatureItem label="Duration" value={`${features.activity_duration_hours} h`} />
            <FeatureItem label="Avg Amount" value={fmtCurrency(features.avg_amount)} />
            <FeatureItem label="Max Amount" value={fmtCurrency(features.max_amount)} />
          </FeatureGroup>
        </div>
      )}

      <div className="rounded-lg border border-slate-800 bg-slate-900">
        <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between flex-wrap gap-2">
          <span className="text-sm font-semibold">Transaction History</span>
          <div className="flex items-center gap-2">
            <div className="flex rounded border border-slate-800 overflow-hidden text-xs">
              <button onClick={() => setOrderAndReload("desc")} className={`px-2 py-1 ${txOrder==="desc" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-400"}`}>Newest</button>
              <button onClick={() => setOrderAndReload("asc")} className={`px-2 py-1 ${txOrder==="asc" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-400"}`}>Oldest</button>
            </div>
            <span className="text-xs text-slate-500">{tx.pagination.total} total</span>
          </div>
        </div>
        <TransactionTable data={tx.data} selectedId={account.id} />
        <div className="flex justify-between p-3">
          <button disabled={txPage === 0} onClick={() => loadTx(Math.max(0, txPage - 10))} className="text-xs px-2 py-1 rounded border border-slate-800 disabled:opacity-30">Prev</button>
          <button disabled={txPage + 10 >= tx.pagination.total} onClick={() => loadTx(txPage + 10)} className="text-xs px-2 py-1 rounded border border-slate-800 disabled:opacity-30">Next</button>
        </div>
        <div className="px-3 pb-2 text-[11px] text-slate-500">Order: {txOrder==="asc" ? "Oldest first — useful for chronological money-flow tracing" : "Newest first"} · Backend supports <code>order=asc/desc</code>.</div>
      </div>

      <div className="rounded-lg border border-slate-800 bg-slate-900">
        <div className="px-4 py-3 border-b border-slate-800 text-sm font-semibold">Connected Accounts</div>
        <ConnectedAccounts data={connected} />
      </div>
    </div>
  );
}
