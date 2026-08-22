import { Routes, Route } from "react-router-dom";
import { lazy, Suspense } from "react";
import Layout from "./components/layout/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Accounts from "./pages/Accounts.jsx";
import AccountDetail from "./pages/AccountDetail.jsx";

const GraphInvestigation = lazy(() => import("./pages/GraphInvestigation.jsx"));

function NotFound() {
  return <div className="p-6 text-center"><h1 className="text-lg font-semibold">404 — Not found</h1><p className="text-sm text-slate-400">The requested page does not exist.</p></div>;
}

function Loading() {
  return <div className="p-6 text-sm text-slate-400">Loading…</div>;
}

export default function App() {
  return (
    <Layout>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/accounts" element={<Accounts />} />
          <Route path="/accounts/:id" element={<AccountDetail />} />
          <Route path="/graph/:id" element={<GraphInvestigation />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </Layout>
  );
}
