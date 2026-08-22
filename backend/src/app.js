import express from "express";
import cors from "cors";
import { config } from "./config.js";
import healthRouter from "./routes/health.js";
import accountsRouter from "./routes/accounts.js";
import graphRouter from "./routes/graph.js";
import statsRouter from "./routes/stats.js";
import { notFound, errorHandler } from "./middleware/errorHandler.js";

const app = express();

app.use(cors({ origin: config.frontendOrigin, credentials: false }));
app.use(express.json());

app.use("/api/health", healthRouter);
app.use("/api/stats", statsRouter);
app.use("/api/accounts", accountsRouter);
app.use("/api/graph", graphRouter);

// 404 for unmatched routes
app.use(notFound);
app.use(errorHandler);

export default app;
