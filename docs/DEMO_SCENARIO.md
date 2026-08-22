# MuleGuard Demo Scenario — Investigator Story

> Language rule: never "proves fraud". Use **suspicious**, **high-risk**, **anomalous**, **requires investigation**.

## Scenario

An investigator reviews overnight alerts. MuleGuard ingested 5184 transactions across 425 accounts. Pipeline flagged 3 CRITICAL, 15 HIGH accounts. The task: understand **why** an account is high-risk and **where its money flows**.

## Step 1 — Dashboard `/`

- Observe KPIs: **Total 425**, **CRITICAL 3**, **HIGH 15**, **MEDIUM 229**, **LOW 178**.
- Pie: distribution from `risk_scores` (ML 40% + Rules 30% + Graph 30%).
- **Top Risk Accounts**: `C0073 86.53 CRITICAL` (high anomaly 89.57 + fan-in 27 + graph 89.02) — note top is a normal hub, not a synthetic mule (honest evaluation).
- Say: "Anomaly ≠ fraud — this is a triage queue."

## Step 2 — Suspicious Accounts `/accounts`

- Table shows `Account | Risk | Final | ML | Rules | Graph | Primary reason`.
- **Search**: type `M0003` (debounced 300ms) → 1 row via `GET /api/accounts?q=M0003` (`ILIKE` parameterized, case-insensitive, prefix/contains).
- **Filter CRITICAL**: dropdown → 3 rows (C0073, C0244, C0231) — confirms `GET /api/accounts?risk_level=CRITICAL`; combine search `M000` + filter `HIGH` → filtered.
- **Sort by ML**: click sort → M0003 (ml 100) rises to top.
- Pagination: 20 per page, `1–20 of 425`.
- Click **C0073** → detail, but we will investigate **M0003** as high-ML mule vs hub.

## Step 3 — Account M0003 `/accounts/M0003`

- Header: `M0003 (Mule M0003) HIGH 64.5 / 100`.
- **Risk Breakdown**:
  ```
  Anomaly (ML)      100.0  ← Isolation Forest 100/100 vs peers
  Behavioral        45.0   ← 2 rules triggered
  Graph             36.67  ← fan-in + chain
  --------------------------
  Final             64.5   (0.4*ML + 0.3*Rules + 0.3*Graph)
  ```
  Demo weighting, not calibrated probability.

- **Why Flagged?** (from `risk.reasons`, not frontend):
  - High anomaly score (100/100) vs peer accounts — unusual behavior.
  - High fan-in: 18 unique incoming counterparties.
  - High fan-in: 18 unique incoming counterparties. (graph)
  - Participates in a 3-account transaction chain (span 92 min) — possible layering.

- **Features**:
  - Volume: Total In ₹31,281, Out ₹0, Tx 18 (18 in / 0 out)
  - Counterparties: 18 senders, 0 receivers — classic fan-in.
  - Activity: velocity 9.64/h (vs normal 0.04/h), duration 1.87h.
  - Amounts: avg ₹1,737 max ₹2,918.

## Step 4 — Transaction Investigation

- **Transaction History** (10 per page, `GET /api/accounts/M0003/transactions?limit=10&order=desc` default **Newest**, toggle **Oldest** → `order=asc` for chronological layering):
  - Table: `Time | Direction (Incoming emerald) | Counterparty (C0148…) | Amount`
  - 18 total, all Incoming from 18 distinct senders within 2h — matches fan-in.
  - Toggle **Newest↔Oldest** (backend supports `order=asc/desc`, trace remains chronological).
  - Toggle `include_synthetic` hidden by default (investigator vs evaluation).

## Step 5 — Connected Accounts

- **GET /api/accounts/M0003/connected** → 18 incoming, each 1 tx, ₹800–₹2,918, first/last.
- Click **C0148** → navigates to its detail (now seen as counterparty).

## Step 6 — Graph Investigation `/graph/M0010`

- Choose **M0010** (synthetic fan-out mule, useful graph). Default `depth 2` → 243 nodes, 363 edges.
- Controls: `Depth 1` → 15 nodes, `Depth 2` → 243, `Depth 3` → 423 (bounded at 3, not unbounded), deterministic positions (sorted final_score DESC→id ASC, 1→2→1 returns same).
- Nodes: `M0010` ROOT indigo, others colored LOW slate / MEDIUM amber / HIGH orange / CRITICAL red + score.
- Edges: arrow `source→target` = money flow, collapsed label `₹11,778` or `₹24.5K · 5 tx`.
- Legend: LOW…CRITICAL + `→ = money flow`.
- Open **M0021** `/graph/M0021?depth=2` → 48 nodes, shows `C0329` and `C0139` — circular pattern members.

## Step 7 — Trace `M0021 → C0139`

- Form: **FROM** `M0021` (pre-filled), **TO** `C0139` (click node or type) → **Trace** → `GET /api/graph/trace?from=M0021&to=C0139&max_depth=4`.
- Result: **found true**
  ```
  M0021
    ↓ T005170 ₹11,778 2026-01-13 00:00
  C0329
    ↓ T005171 ₹11,618 2026-01-13 00:12
  C0139
    ↓ (next hop would close cycle back to M0021)
  ```
  Path highlighted green in graph, de-emphasized others not rebuilt.

- **No path**: `M0003 → C0001` → `No directed money-flow path found within the selected depth.` (200, not error) — demonstrates sparse connectivity.

## Step 8 — Explain

- MuleGuard combines:
  1. **Isolation Forest** (unsupervised, 14 account features, never sees `is_fraud_label`) → `ml_score`
  2. **Explainable rules** (fan-in >15, fan-out >12, velocity >1/h, rapid drain, etc.) → `rule_score` + reasons
  3. **Graph intelligence** (MultiDiGraph, 200 chains, 500 cycles, betweenness) → `graph_score` + reasons

- Weights `40/30/30` are demo, not validated — `docs/ML_EVALUATION.md` shows honest `mule recall@25 5/25=20%` (Phase 2 graph boosted normal hubs, `C0073` top). Strength: demonstrates evaluation not hidden.

- Close: "This queue is **suspicious, high-risk, requires investigation** — not proof of fraud. Next: PaySim ingestion, auth, deployment."

## What not to demo

- No fake data (all 425 from `GET /api/stats` / DB).
- No login yet (Phase 6).
- No PaySim (separate phase).
