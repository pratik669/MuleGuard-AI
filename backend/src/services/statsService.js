import { pool } from "../db.js";

export async function getStats() {
  const totalRes = await pool.query("SELECT COUNT(*) FROM risk_scores");
  const total_accounts = parseInt(totalRes.rows[0].count, 10);

  const distRes = await pool.query("SELECT risk_level, COUNT(*) as cnt FROM risk_scores GROUP BY risk_level");
  const risk_distribution = { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 };
  for (const row of distRes.rows) {
    risk_distribution[row.risk_level] = parseInt(row.cnt, 10);
  }

  const topRes = await pool.query(
    `SELECT a.id as account_id, a.name, a.type, a.created_at,
            r.final_score, r.risk_level, r.ml_score, r.rule_score, r.graph_score, r.reasons
     FROM risk_scores r
     JOIN accounts a ON a.id = r.account_id
     ORDER BY r.final_score DESC, r.account_id ASC
     LIMIT 10`
  );
  const top_risk_accounts = topRes.rows.map(r => ({
    account_id: r.account_id,
    name: r.name,
    type: r.type,
    created_at: r.created_at,
    final_score: parseFloat(r.final_score),
    risk_level: r.risk_level,
    ml_score: parseFloat(r.ml_score),
    rule_score: parseFloat(r.rule_score),
    graph_score: parseFloat(r.graph_score),
    reasons: r.reasons
  }));

  return { total_accounts, risk_distribution, top_risk_accounts };
}
