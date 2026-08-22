import app from "./app.js";
import { config } from "./config.js";
import { pool } from "./db.js";

app.listen(config.port, () => {
  console.log(`MuleGuard backend listening on http://localhost:${config.port}`);
});

process.on("SIGTERM", async () => {
  await pool.end();
  process.exit(0);
});
