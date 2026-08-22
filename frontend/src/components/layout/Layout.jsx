import { NavLink, useNavigate } from "react-router-dom";
import { Shield, LayoutDashboard, Users, Search } from "lucide-react";
import { useState } from "react";

export default function Layout({ children }) {
  const [q, setQ] = useState("");
  const nav = useNavigate();
  const onSearch = (e) => {
    e.preventDefault();
    if (q.trim()) nav(`/accounts/${q.trim().toUpperCase()}`);
  };
  const linkCls = ({ isActive }) =>
    `flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition ${isActive ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white hover:bg-slate-800/60"}`;
  return (
    <div className="min-h-screen bg-[#020617] text-slate-200 flex flex-col">
      <header className="h-14 border-b border-slate-800 bg-slate-950/80 backdrop-blur flex items-center justify-between px-4 sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-indigo-600 flex items-center justify-center"><Shield size={16} className="text-white" /></div>
          <span className="font-semibold tracking-tight">MuleGuard</span>
          <span className="text-xs text-slate-500 hidden sm:inline">Investigation Console</span>
        </div>
        <form onSubmit={onSearch} className="flex items-center gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-2.5 text-slate-500" />
            <input value={q} onChange={e => setQ(e.target.value)} placeholder="Go to account (e.g. M0003)" className="pl-8 pr-3 py-1.5 bg-slate-900 border border-slate-800 rounded-md text-sm w-64 focus:outline-none focus:border-indigo-600 placeholder:text-slate-500" />
          </div>
        </form>
      </header>
      <div className="flex flex-1">
        <aside className="w-56 border-r border-slate-800 bg-slate-950 hidden md:flex flex-col p-3 gap-1">
          <NavLink to="/" className={linkCls}><LayoutDashboard size={16} /> Dashboard</NavLink>
          <NavLink to="/accounts" className={linkCls}><Users size={16} /> Accounts</NavLink>
          <div className="mt-auto pt-4 border-t border-slate-800 text-xs text-slate-500">
            <div>ML + Rules + Graph</div>
            <div className="text-[11px]">Anomaly ≠ fraud</div>
          </div>
        </aside>
        <main className="flex-1 min-w-0 bg-[#020617]">{children}</main>
      </div>
    </div>
  );
}
