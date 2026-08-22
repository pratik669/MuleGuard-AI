import { Router } from "express";
import { checkDb } from "../db.js";
const router = Router();
router.get("/", async (req, res) => {
  try {
    await checkDb();
    res.json({ status: "ok", database: "connected", timestamp: new Date().toISOString() });
  } catch (e) {
    res.status(500).json({ status: "error", database: "disconnected", error: e.message });
  }
});
export default router;
