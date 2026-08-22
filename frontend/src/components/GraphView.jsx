import ReactFlow, { Background, Controls, MarkerType, useReactFlow } from "reactflow";
import "reactflow/dist/style.css";
import { useMemo } from "react";

const riskFill = { LOW: "#334155", MEDIUM: "#f59e0b", HIGH: "#f97316", CRITICAL: "#ef4444" };

function RiskNode({ data }) {
  const isRoot = data.isRoot;
  const fill = riskFill[data.risk_level] || "#334155";
  return (
    <div className={`px-3 py-2 rounded-lg border bg-slate-900 text-xs min-w-[110px] ${isRoot ? "border-indigo-500 shadow-lg shadow-indigo-900/30" : "border-slate-700"}`}>
      <div className="font-mono font-semibold flex items-center justify-between gap-2">
        <span>{data.label}</span>
        {isRoot && <span className="text-[10px] bg-indigo-600 text-white px-1 rounded">ROOT</span>}
      </div>
      <div className="flex items-center gap-1.5 mt-1">
        <span className="w-2 h-2 rounded-full" style={{ background: fill }} />
        <span className="text-[11px]">{data.risk_level || "UNKNOWN"}</span>
        <span className="text-[11px] text-slate-400">{data.final_score != null ? Number(data.final_score).toFixed(1) : "-"}</span>
      </div>
    </div>
  );
}
const nodeTypes = { risk: RiskNode };

export default function GraphView({ graphData, onNodeClick, highlightPath }) {
  const { nodes, edges } = graphData || { nodes: [], edges: [] };
  const highlightSet = useMemo(() => new Set(highlightPath || []), [highlightPath]);

  const sortedNodes = useMemo(() => {
    // deterministic: final_score DESC then id ASC (stable)
    return [...nodes].sort((a, b) => {
      const fa = a.final_score ?? -1, fb = b.final_score ?? -1;
      if (fb !== fa) return fb - fa;
      return a.id.localeCompare(b.id);
    });
  }, [nodes]);

  const rfNodes = useMemo(() => {
    // deterministic circular layout
    return sortedNodes.map((n, i) => {
      const angle = (i / Math.max(1, sortedNodes.length)) * 2 * Math.PI;
      const r = Math.min(280, 120 + sortedNodes.length * 4);
      const x = 400 + Math.cos(angle) * r;
      const y = 300 + Math.sin(angle) * r;
      const isHighlighted = highlightSet.has(n.id);
      return {
        id: n.id,
        type: "risk",
        position: { x, y },
        data: { label: n.id, risk_level: n.risk_level, final_score: n.final_score, isRoot: n.id === graphData.root },
        style: isHighlighted ? { borderColor: "#22c55e", borderWidth: 2 } : undefined,
      };
    });
  }, [sortedNodes, graphData, highlightSet]);

  const rfEdges = useMemo(() => edges.map((e, i) => {
    const isHl = highlightSet.has(e.source) && highlightSet.has(e.target);
    const label = e.transaction_count > 1 ? `₹${(e.total_amount/1000).toFixed(1)}K · ${e.transaction_count} tx` : `₹${Number(e.total_amount).toFixed(0)}`;
    return {
      id: `e-${i}-${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      label,
      labelStyle: { fontSize: 10, fill: "#94a3b8" },
      labelBgStyle: { fill: "#0f172a" },
      markerEnd: { type: MarkerType.ArrowClosed, color: isHl ? "#22c55e" : "#64748b" },
      style: { stroke: isHl ? "#22c55e" : "#475569", strokeWidth: isHl ? 2.5 : 1.2 },
    };
  }), [edges, highlightSet]);

  if (!nodes.length) return <div className="text-sm text-slate-500 p-6">No graph data.</div>;
  return (
    <div className="h-[520px] rounded-lg border border-slate-800 bg-slate-950 overflow-hidden">
      <ReactFlow nodes={rfNodes} edges={rfEdges} nodeTypes={nodeTypes} onNodeClick={(_, n) => onNodeClick && onNodeClick(n.id)} fitView>
        <Background color="#1e293b" gap={16} />
        <Controls />
      </ReactFlow>
    </div>
  );
}
