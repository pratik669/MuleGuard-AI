import { Router } from "express";
import { parseAccountsQuery, listAccounts, getAccountById, getTransactions, getConnected } from "../services/accountService.js";

const router = Router();

// GET /api/accounts
router.get("/", async (req, res, next) => {
  try {
    const parsed = parseAccountsQuery(req.query);
    const { data, total } = await listAccounts(parsed);
    res.json({
      data: data.map(r => ({
        account_id: r.id,
        name: r.name,
        type: r.type,
        created_at: r.created_at,
        final_score: r.final_score != null ? parseFloat(r.final_score) : null,
        risk_level: r.risk_level,
        ml_score: r.ml_score != null ? parseFloat(r.ml_score) : null,
        rule_score: r.rule_score != null ? parseFloat(r.rule_score) : null,
        graph_score: r.graph_score != null ? parseFloat(r.graph_score) : null,
        reasons: r.reasons
      })),
      pagination: { limit: parsed.limit, offset: parsed.offset, total }
    });
  } catch (e) { next(e); }
});

// GET /api/accounts/:id/transactions (must be before :id)
router.get("/:id/transactions", async (req, res, next) => {
  try {
    const id = req.params.id;
    const limitRaw = req.query.limit ?? "50";
    const offsetRaw = req.query.offset ?? "0";
    const order = (req.query.order || "desc").toString().toLowerCase();
    let limit = parseInt(limitRaw, 10);
    let offset = parseInt(offsetRaw, 10);
    if (isNaN(limit) || limit < 1 || limit > 100) throw Object.assign(new Error("Invalid limit: 1-100"), { status: 400 });
    if (isNaN(offset) || offset < 0) throw Object.assign(new Error("Invalid offset: >=0"), { status: 400 });
    if (!["asc", "desc"].includes(order)) throw Object.assign(new Error("Invalid order: asc/desc"), { status: 400 });
    const result = await getTransactions(id, { limit, offset, order });
    if (result === null) return res.status(404).json({ error: `Account ${id} not found` });
    const includeSynthetic = req.query.include_synthetic === "1" || req.query.include_synthetic === "true";
    const data = result.data.map(r => {
      const base = { id: r.id, from_account: r.from_account, to_account: r.to_account, amount: parseFloat(r.amount), timestamp: r.timestamp, type: r.type };
      if (includeSynthetic) base.synthetic_label = r.is_fraud_label;
      return base;
    });
    res.json({ data, pagination: { limit, offset, total: result.total } });
  } catch (e) { next(e); }
});

// GET /api/accounts/:id/connected
router.get("/:id/connected", async (req, res, next) => {
  try {
    const id = req.params.id;
    const result = await getConnected(id);
    if (result === null) return res.status(404).json({ error: `Account ${id} not found` });
    res.json({ data: { account_id: id, connected: result } });
  } catch (e) { next(e); }
});

// GET /api/accounts/:id
router.get("/:id", async (req, res, next) => {
  try {
    const id = req.params.id;
    const data = await getAccountById(id);
    if (!data) return res.status(404).json({ error: `Account ${id} not found` });
    res.json({ data });
  } catch (e) { next(e); }
});

export default router;
