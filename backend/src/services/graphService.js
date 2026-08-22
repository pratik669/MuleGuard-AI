import { pool } from "../db.js";

export async function accountExists(id) {
  const r = await pool.query("SELECT 1 FROM accounts WHERE id = $1", [id]);
  return r.rows.length > 0;
}

export async function getGraph(rootId, depth) {
  if (!(await accountExists(rootId))) return null;

  // BFS bounded traversal, fetching edges via ANY(array) to avoid placeholder mismatches
  let visited = new Set([rootId]);
  let frontier = new Set([rootId]);
  const allNodes = new Set([rootId]);
  const edges = [];

  for (let d = 0; d < depth; d++) {
    if (frontier.size === 0) break;
    const ids = [...frontier];
    const res = await pool.query(
      `SELECT id, from_account, to_account, amount, timestamp FROM transactions WHERE from_account = ANY($1) OR to_account = ANY($1)`,
      [ids]
    );
    const nextFrontier = new Set();
    for (const row of res.rows) {
      const a = row.from_account, b = row.to_account;
      // only include edge if at least one endpoint in current frontier
      if (!frontier.has(a) && !frontier.has(b)) continue;
      edges.push(row);
      for (const nid of [a, b]) {
        if (!visited.has(nid)) {
          visited.add(nid);
          allNodes.add(nid);
          nextFrontier.add(nid);
        }
        allNodes.add(nid);
      }
    }
    frontier = nextFrontier;
  }

  // fetch node metadata (accounts + risk)
  const allIds = [...allNodes];
  const nodeRes = await pool.query(
    `SELECT a.id, a.name, r.final_score, r.risk_level FROM accounts a LEFT JOIN risk_scores r ON r.account_id = a.id WHERE a.id = ANY($1)`,
    [allIds]
  );
  const nodes = nodeRes.rows.map(r => ({
    id: r.id,
    label: r.name || r.id,
    risk_level: r.risk_level || null,
    final_score: r.final_score != null ? parseFloat(r.final_score) : null
  }));

  // collapse edges by (from,to) for cleaner React Flow
  const collapsed = new Map();
  for (const e of edges) {
    const key = `${e.from_account}->${e.to_account}`;
    if (!collapsed.has(key)) collapsed.set(key, { source: e.from_account, target: e.to_account, transaction_count: 0, total_amount: 0, first_seen: e.timestamp, last_seen: e.timestamp });
    const c = collapsed.get(key);
    c.transaction_count += 1;
    c.total_amount += parseFloat(e.amount);
    if (e.timestamp < c.first_seen) c.first_seen = e.timestamp;
    if (e.timestamp > c.last_seen) c.last_seen = e.timestamp;
  }

  // also include raw direction preserved
  return {
    root: rootId,
    depth,
    nodes,
    edges: [...collapsed.values()]
  };
}

export async function tracePath(from, to, maxDepth) {
  if (!(await accountExists(from))) return { error: `from account ${from} not found`, status: 404 };
  if (!(await accountExists(to))) return { error: `to account ${to} not found`, status: 404 };
  if (from === to) return { data: { from, to, found: true, path: [{ account_id: from }], transactions: [] } };

  // Load all transactions once (5184 edges) and BFS directed
  const res = await pool.query("SELECT id, from_account, to_account, amount, timestamp FROM transactions ORDER BY timestamp ASC");
  const adj = new Map(); // from -> list of edges
  for (const row of res.rows) {
    if (!adj.has(row.from_account)) adj.set(row.from_account, []);
    adj.get(row.from_account).push(row);
  }

  // BFS
  const queue = [{ path: [from], txs: [], visited: new Set([from]) }];
  let head = 0;
  while (head < queue.length) {
    const cur = queue[head++];
    const last = cur.path[cur.path.length - 1];
    if (cur.path.length - 1 >= maxDepth) continue;
    const outs = adj.get(last) || [];
    for (const edge of outs) {
      const nxt = edge.to_account;
      if (cur.visited.has(nxt)) continue;
      const newPath = [...cur.path, nxt];
      const newTxs = [...cur.txs, { id: edge.id, from_account: edge.from_account, to_account: edge.to_account, amount: parseFloat(edge.amount), timestamp: edge.timestamp }];
      if (nxt === to) {
        return {
          data: {
            from, to, found: true,
            path: newPath.map(id => ({ account_id: id })),
            transactions: newTxs
          }
        };
      }
      const newVisited = new Set(cur.visited);
      newVisited.add(nxt);
      queue.push({ path: newPath, txs: newTxs, visited: newVisited });
      if (queue.length > 5000) break; // safety cap
    }
    if (queue.length > 5000) break;
  }

  return { data: { from, to, found: false, path: [], transactions: [] } };
}
