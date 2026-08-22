import dotenv from "dotenv";
import path from "path";
import { fileURLToPath } from "url";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.resolve(__dirname, "../../.env") });
dotenv.config();
export const config = {
  port: parseInt(process.env.BACKEND_PORT || process.env.PORT || "4000", 10),
  dbUrl: process.env.DATABASE_URL || "postgresql://postgres:postgres@localhost:5432/muleguard",
  frontendOrigin: process.env.FRONTEND_ORIGIN || "http://localhost:5173"
};
