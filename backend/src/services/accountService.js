import { pool } from "../db.js";

const SORT_MAP = {
  risk: "r.final_score",
  ml_score: "r.ml_score",
  rule_score: "r.rule_score",
  graph_score: "r.graph_score",
  account_id: "a.id",
  final_score: "r.final_score"
};
const RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

export function parseAccountsQuery(q) {
  const sort = (q.sort || "risk").toString();
  const order = (q.order || "desc").toString().toLowerCase();
  const risk_level = q.risk_level ? q.risk_level.toString().toUpperCase() : null;
  const rawQ = q.q != null ? q.q.toString().trim() : "";
  const search = rawQ.length > 0 ? rawQ.slice(0, 50) : null;
  let limit = parseInt(q.limit ?? "50", 10);
  let offset = parseInt(q.offset ?? "0", 10);

  if (!SORT_MAP[sort]) throw Object.assign(new Error(`Invalid sort: ${sort}. Allowed: ${Object.keys(SORT_MAP).join(", ")}`), { status: 400 });
  if (!["asc", "desc"].includes(order)) throw Object.assign(new Error("Invalid order: must be asc or desc"), { status: 400 });
  if (risk_level && !RISK_LEVELS.includes(risk_level)) throw Object.assign(new Error(`Invalid risk_level: ${risk_level}`), { status: 400 });
  if (isNaN(limit) || limit < 1 || limit > 100) throw Object.assign(new Error("Invalid limit: must be 1-100"), { status: 400 });
  if (isNaN(offset) || offset < 0) throw Object.assign(new Error("Invalid offset: must be >=0"), { status: 400 });

  return { sort, order, risk_level, search, limit, offset };
}

export async function listAccounts({ sort, order, risk_level, search, limit, offset }) {
  const sortCol = SORT_MAP[sort];
  const dir = order === "asc" ? "ASC" : "DESC";

  const where = [];
  const params = [];
  let idx = 1;
  if (risk_level) {
    where.push(`r.risk_level = $${idx++}`);
    params.push(risk_level);
  }
  if (search) {
    where.push(`(a.id ILIKE '%' || $${idx} || '%' OR a.name ILIKE '%' || $${idx} || '%')`);
    params.push(search);
    idx++;
  }
  const whereClause = where.length ? `WHERE ${where.join(" AND ")}` : "";

  // count
  const countRes = await pool.query(`SELECT COUNT(*) FROM accounts a JOIN risk_scores r ON r.account_id = a.id ${whereClause}`, params);
  const total = parseInt(countRes.rows[0].count, 10);

  // data — parameterized sort via whitelist, dir via whitelist, limit/offset via params
  const dataParams = [...params, limit, offset];
  const limitPos = idx++;
  const offsetPos = idx++;
  const dataRes = await pool.query(
    `SELECT a.id, a.name, a.type, a.created_at,
            r.final_score, r.risk_level, r.ml_score, r.rule_score, r.graph_score, r.reasons
     FROM accounts a
     JOIN risk_scores r ON r.account_id = a.id
     ${whereClause}
     ORDER BY ${sortCol} ${dir}, a.id ASC
     LIMIT $${limitPos} OFFSET $${offsetPos}`,
    dataParams
  );
  return { data: dataRes.rows, total };
}

export async function getAccountById(id) {
  const accRes = await pool.query(
    `SELECT a.id, a.name, a.type, a.created_at,
            r.final_score, r.risk_level, r.ml_score, r.rule_score, r.graph_score, r.reasons,
            f.total_in, f.total_out, f.cnt_in, f.cnt_out, f.unique_senders, f.unique_receivers,
            f.avg_amount, f.max_amount, f.tx_count, f.inflow_outflow_ratio, f.fan_in_score, f.fan_out_score,
            f.activity_duration_hours, f.velocity_per_hour
     FROM accounts a
     LEFT JOIN risk_scores r ON r.account_id = a.id
     LEFT JOIN account_features f ON f.account_id = a.id
     WHERE a.id = $1`,
    [id]
  );
  if (accRes.rows.length === 0) return null;
  const row = accRes.rows[0];
  return {
    account: { id: row.id, name: row.name, type: row.type, created_at: row.created_at },
    risk: {
      final_score: row.final_score != null ? parseFloat(row.final_score) : null,
      risk_level: row.risk_level,
      ml_score: row.ml_score != null ? parseFloat(row.ml_score) : null,
      rule_score: row.rule_score != null ? parseFloat(row.rule_score) : null,
      graph_score: row.graph_score != null ? parseFloat(row.graph_score) : null,
      reasons: row.reasons || []
    },
    features: row.total_in != null ? {
      total_in: parseFloat(row.total_in),
      total_out: parseFloat(row.total_out),
      cnt_in: row.cnt_in,
      cnt_out: row.cnt_out,
      unique_senders: row.unique_senders,
      unique_receivers: row.unique_receivers,
      avg_amount: parseFloat(row.avg_amount),
      max_amount: parseFloat(row.max_amount),
      tx_count: row.tx_count,
      inflow_outflow_ratio: parseFloat(row.inflow_outflow_ratio),
      fan_in_score: row.fan_in_score,
      fan_out_score: row.fan_out_score,
      activity_duration_hours: parseFloat(row.activity_duration_hours),
      velocity_per_hour: parseFloat(row.velocity_per_hour)
    } : null
  };
}

export async function getTransactions(accountId, { limit, offset, order }) {
  // validate account exists
  const exists = await pool.query("SELECT 1 FROM accounts WHERE id = $1", [accountId]);
  if (exists.rows.length === 0) return null;

  const dir = order === "asc" ? "ASC" : "DESC";
  const countRes = await pool.query(
    "SELECT COUNT(*) FROM transactions WHERE from_account = $1 OR to_account = $1",
    [accountId]
  );
  const total = parseInt(countRes.rows[0].count, 10);

  const res = await pool.query(
    `SELECT id, from_account, to_account, amount, timestamp, type, is_fraud_label
     FROM transactions
     WHERE from_account = $1 OR to_account = $1
     ORDER BY timestamp ${dir}
     LIMIT $2 OFFSET $3`,
    [accountId, limit, offset]
  );
  return { data: res.rows, total };
}

export async function getConnected(accountId) {
  const exists = await pool.query("SELECT 1 FROM accounts WHERE id = $1", [accountId]);
  if (exists.rows.length === 0) return null;

  const res = await pool.query(
    `SELECT
       CASE WHEN from_account = $1 THEN to_account ELSE from_account END as counterparty,
       CASE WHEN from_account = $1 THEN 'outgoing' ELSE 'incoming' END as direction,
       COUNT(*) as transaction_count,
       SUM(amount) as total_amount,
       MIN(timestamp) as first_seen,
       MAX(timestamp) as last_seen
     FROM transactions
     WHERE from_account = $1 OR to_account = $1
     GROUP BY counterparty, direction
     ORDER BY total_amount DESC`,
    [accountId]
  );
  return res.rows.map(r => ({
    account_id: r.counterparty,
    direction: r.direction,
    transaction_count: parseInt(r.transaction_count, 10),
    total_amount: parseFloat(r.total_amount),
    first_seen: r.first_seen,
    last_seen: r.last_seen
  }));
}
