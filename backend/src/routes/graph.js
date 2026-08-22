import { Router } from "express";
import { getGraph, tracePath } from "../services/graphService.js";

const router = Router();

// GET /api/graph/trace?from=A&to=B&max_depth=4  (must be before :id)
router.get("/trace", async (req, res, next) => {
  try {
    const from = req.query.from?.toString();
    const to = req.query.to?.toString();
    let maxDepth = parseInt(req.query.max_depth ?? "4", 10);
    if (!from || !to) throw Object.assign(new Error("Missing required query params: from, to"), { status: 400 });
    if (isNaN(maxDepth) || maxDepth < 1 || maxDepth > 6) throw Object.assign(new Error("Invalid max_depth: 1-6"), { status: 400 });
    const result = await tracePath(from, to, maxDepth);
    if (result.error) return res.status(result.status || 404).json({ error: result.error });
    res.json(result);
  } catch (e) { next(e); }
});

// GET /api/graph/:id?depth=2
router.get("/:id", async (req, res, next) => {
  try {
    const id = req.params.id;
    let depth = parseInt(req.query.depth ?? "2", 10);
    if (isNaN(depth) || depth < 1 || depth > 3) throw Object.assign(new Error("Invalid depth: 1-3"), { status: 400 });
    const data = await getGraph(id, depth);
    if (data === null) return res.status(404).json({ error: `Account ${id} not found` });
    res.json({ data });
  } catch (e) { next(e); }
});

export default router;
