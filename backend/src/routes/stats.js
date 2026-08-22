import { Router } from "express";
import { getStats } from "../services/statsService.js";
const router = Router();
router.get("/", async (req, res, next) => {
  try {
    const data = await getStats();
    res.json({ data });
  } catch (e) { next(e); }
});
export default router;
