import pg from "pg";
import { config } from "./config.js";
const { Pool } = pg;
export const pool = new Pool({
  connectionString: config.dbUrl
});
export async function checkDb() {
  const client = await pool.connect();
  try {
    await client.query("SELECT 1");
    return true;
  } finally {
    client.release();
  }
}
