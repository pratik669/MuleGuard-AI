import { useEffect, useState } from "react";
import { getAccounts } from "../api/accounts.js";
import AccountTable from "../components/AccountTable.jsx";

export default function Accounts() {
  const [data, setData] = useState([]);
  const [pagination, setPagination] = useState({ total: 0, limit: 20, offset: 0 });
  const [sort, setSort] = useState("risk");
  const [order, setOrder] = useState("desc");
  const [risk, setRisk] = useState("");
  const [input, setInput] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  useEffect(() => {
    const t = setTimeout(() => setSearch(input.trim()), 300);
    return () => clearTimeout(t);
  }, [input]);

  const fetchData = async (off = 0) => {
    setLoading(true); setErr(null);
    try {
      const res = await getAccounts({ sort, order, risk_level: risk || undefined, q: search || undefined, limit: pagination.limit, offset: off });
      setData(res.data);
      setPagination(prev => ({ ...prev, total: res.pagination.total, offset: off }));
    } catch (e) {
      const msg = e.message === "Failed to fetch" ? "Unable to connect to MuleGuard API. Is the backend running on http://localhost:4000?" : e.message;
      setErr(msg);
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchData(0); }, [sort, order, risk, search]);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Suspicious Accounts</h1>
        <div className="text-xs text-slate-500">{pagination.total} accounts</div>
      </div>

      <div className="flex flex-wrap gap-2 items-center">
        <input value={input} onChange={e => setInput(e.target.value)} placeholder="Search by ID or name (e.g. M0003)" className="bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-sm w-64 placeholder:text-slate-500 focus:outline-none focus:border-indigo-600" />
        <select value={sort} onChange={e => setSort(e.target.value)} className="bg-slate-900 border border-slate-800 rounded px-2 py-1.5 text-sm">
          <option value="risk">Sort: Final risk</option>
          <option value="ml_score">Sort: ML</option>
          <option value="rule_score">Sort: Rules</option>
          <option value="graph_score">Sort: Graph</option>
          <option value="account_id">Sort: ID</option>
        </select>
        <select value={order} onChange={e => setOrder(e.target.value)} className="bg-slate-900 border border-slate-800 rounded px-2 py-1.5 text-sm">
          <option value="desc">Desc</option>
          <option value="asc">Asc</option>
        </select>
        <select value={risk} onChange={e => setRisk(e.target.value)} className="bg-slate-900 border border-slate-800 rounded px-2 py-1.5 text-sm">
          <option value="">All levels</option>
          <option value="CRITICAL">CRITICAL</option>
          <option value="HIGH">HIGH</option>
          <option value="MEDIUM">MEDIUM</option>
          <option value="LOW">LOW</option>
        </select>
      </div>

      {loading ? <div className="text-sm text-slate-400 p-6">Loading…</div> : err ? <div className="text-sm text-red-400 p-6">{err}</div> : <AccountTable data={data} />}

      <div className="flex items-center justify-between">
        <button disabled={pagination.offset === 0} onClick={() => fetchData(Math.max(0, pagination.offset - pagination.limit))} className="px-3 py-1.5 rounded border border-slate-800 bg-slate-900 text-sm disabled:opacity-40">Prev</button>
        <span className="text-xs text-slate-400">{pagination.offset + 1}–{Math.min(pagination.offset + pagination.limit, pagination.total)} of {pagination.total}</span>
        <button disabled={pagination.offset + pagination.limit >= pagination.total} onClick={() => fetchData(pagination.offset + pagination.limit)} className="px-3 py-1.5 rounded border border-slate-800 bg-slate-900 text-sm disabled:opacity-40">Next</button>
      </div>
    </div>
  );
}
