# MuleGuard

AI-assisted financial mule-account detection and investigation platform.

Detects suspicious accounts via **Isolation Forest (unsupervised)** + **explainable behavioral rules** + **graph intelligence** + **risk scoring**, with PostgreSQL + Express API + React investigator console.

> **Important limitation:** Anomaly detection does NOT equal fraud detection. The system identifies unusual behavior that requires investigation.

## Architecture

```
Data (seed 42)
  ↓
PostgreSQL (accounts 425, transactions 5184)
  ↓
Feature Engineering (14 account-level features)
  ↓
Isolation Forest (sklearn, contamination 0.08, unsupervised, no labels) → ml_score 0-100
  ↓
Behavioral Rules (fan-in/out, velocity, rapid drain, etc.) → rule_score + reasons
  ↓
Graph Intelligence (NetworkX MultiDiGraph, chains, cycles 2-4, betweenness, PageRank) → graph_score + reasons
  ↓
Risk Engine (ML 40% + Rules 30% + Graph 30% → final_score + risk_level + reasons) → risk_scores
  ↓
REST API (Express, parameterized SQL, /api/*)
  ↓
React Investigator Console (Vite, React Flow, Recharts, dark, lazy-loaded)
```

## Current Status — Phase 6 Investigator UX & Demo Reliability (2026-08-22)

**Stable end-to-end MVP:** Phases 0–5 preserved, polished (no ML/weights/schema change).

- [x] Synthetic data 425/5184 seed 42 (5 mule patterns A-E)
- [x] PostgreSQL schema + indexes (`transactions` from/to/timestamp, `risk_scores` final_score/risk_level)
- [x] Feature engineering 14 cols (handles zero-div)
- [x] Isolation Forest unsupervised `ml/model.py:19` (no label)
- [x] Rules 7 explainable `ml/rules.py:9`
- [x] Graph `ml/graph_analysis.py:20` (MultiDiGraph, 200 chains gap 180m, 500 cycles 2-4 bounded, betweenness exact, PageRank not scored, WCC 1)
- [x] Risk `ml/risk.py:9` `0.4/0.3/0.3` sum 1.0 (demo, not validated)
- [x] Pipeline 7 steps `python ml/run_pipeline.py` (deterministic, `risk_scores` CRITICAL 3 HIGH15 MEDIUM229 LOW178)
- [x] REST API `backend/src/routes/*` + `services/*` — `/api/health`, `/api/stats`, `/api/accounts?q` search (ILIKE parameterized), `/:id`, `/:id/transactions?order=asc/desc`, `/:id/connected`, `/graph/:id?depth=2` deterministic, `/graph/trace?from&to`
  - Validation whitelist sort, order, risk_level, limit 1-100, depth 1-3, max_depth 1-6; parameterized `ANY($1)` + `ILIKE '%' || $1 || '%'`; CORS `FRONTEND_ORIGIN`; no stack traces
- [x] `GET /api/stats` aggregate (COUNT, GROUP BY, top 10) — Dashboard now 1 call (was 5)
- [x] Dashboard `/` (KPIs, top 10, pie Recharts real data), Accounts `/accounts` **search by ID/name** (debounced `q`, `ILIKE`), sort/filter/pagination, Account `/:id` (RiskGauge, Why Flagged?, FeatureGroups, **Transactions Newest/Oldest toggle** `order=asc/desc`, skeleton loading), Graph `/graph/:id` (**deterministic** final_score DESC → id ASC circular layout, React Flow, depth 1-3, legend, trace `M0021→C0329→C0139` highlight)
- [x] Bundle split: initial `≈195kB` (30kB + vendor 164kB) + lazy `reactflow 131kB` + `recharts 344kB` + `GraphInvestigation 7kB` (was 677kB monolith) via `lazy()` + `manualChunks` `frontend/vite.config.js:10`
- [x] API tests `backend/tests/api.test.js` **35 pass** (30 + search `q=M0003`, nonexistent, filter+q, malicious `q=' OR '1'='1`, boundary 1/100/101, offset, depth 1/3/4, trace 6/7, invalid order, unknown 404, stats)
- [x] ML tests `ml/test_phase2.py` 9 pass
- [x] Frontend build `npm run build --prefix frontend` chunk split verified
- [x] Docs: `docs/API.md` (search `q`), `docs/DEMO_CHECKLIST.md` (search, toggle, deterministic graph), `docs/DEMO_SCENARIO.md` (chronological trace), `docs/ML_EVALUATION.md` (20% recall preserved)
- [x] Repo hygiene: root `package-lock/postcss/tailwind` duplicates removed, `.gitignore` correct

## Prerequisites

- Node 24.14.1, npm 11.19.0
- Python 3.14.3, `psycopg[binary] 3.3.4`, `pandas 2.3.3`, `scikit-learn 1.9.0`, `networkx 3.6.1`
- PostgreSQL 18.4, `psql` in PATH
- Ports 4000 (backend) 5173 (frontend)

## Running Locally

### 1. Env

```bash
git clone https://github.com/Shrikant-Dapke/MuleGuard.git
cd MuleGuard
cp .env.example .env
cp frontend/.env.example frontend/.env  # optional: VITE_API_URL=http://localhost:4000/api for production
# .env requires: DATABASE_URL=postgresql://postgres:postgres@localhost:5432/muleguard, BACKEND_PORT=4000, FRONTEND_ORIGIN=http://localhost:5173
```

### 2. Python

```bash
pip install -r ml/requirements.txt
```

### 3. Database

```bash
psql -U postgres -h localhost -d postgres -c "CREATE DATABASE muleguard;"
psql -U postgres -h localhost -d muleguard -f db/schema.sql
```

### 4. Data + Pipeline (deterministic)

```bash
python ml/generate_data.py   # 425/5184 seed 42
python ml/load_data.py       # idempotent
python ml/run_pipeline.py    # 7 steps, prints CRITICAL 3 HIGH15 etc.
```

### 5. Backend

```bash
cd backend && npm install && npm run dev
# http://localhost:4000/api/health → {status:"ok"}
# Tests: node tests/api.test.js  # 29 pass
```

### 6. Frontend

```bash
cd frontend && npm install && npm run dev
# http://localhost:5173/
# Build: npm run build  # split verified
```

## Detection Model

- **ML:** `ml_score 0-100` higher = more anomalous vs peers. `contamination 0.08`, `StandardScaler`, ratio 99th cap. **Not probability.**
- **Features 14:** `total_in/out`, `cnt_in/out`, `unique_senders/receivers`, `avg/max`, `tx_count`, `inflow_outflow_ratio`, `fan_in/out`, `duration`, `velocity`.
- **Rules:** fan-in>15, fan-out>12, velocity>1/h, rapid drain 90-98% in <10m, counterparty>20, tx>30, amount spike 2.5×.
- **Graph:** fan 25+25, betweenness 10, chain 20, cycle 20 → `graph_score` capped 100. PageRank computed not scored. Chains 200 (greedy gap 180m), cycles 500 (bounded adjacency).
- **Risk:** `final = 0.4*ml + 0.3*rule + 0.3*graph` demo, weights `ml/risk.py:9`. Levels 0-29 LOW 30-59 MEDIUM 60-79 HIGH 80-100. Reasons verbatim backend.

## Demo Workflow

See `docs/DEMO_CHECKLIST.md` (step-by-step) and `docs/DEMO_SCENARIO.md` (8-step investigator story, now with search + chronological toggle + deterministic graph).

Quick path:
1. `/` → KPIs + Top Risk (C0073 86.53 CRITICAL) + pie (1 `GET /api/stats`)
2. `/accounts` → search `M0003` → 1 result ( `GET /api/accounts?q=M0003` ) ; filter `risk_level=CRITICAL` → 3
3. `/accounts/M0003` → HIGH 64.5, ml 100, rule 45, graph 36.67, fan-in 18, chain 92m, features; skeleton while loading
4. Transactions 18 → toggle **Oldest** (`order=asc`) for chronological layering vs **Newest** (`desc`) ; Connected 18 → click C0148
5. `/graph/M0010?depth=2` → 243 nodes, deterministic positions (final_score DESC→id ASC), toggle 1→2→1 returns same positions, legend
6. `/graph/M0021` → trace `M0021→C0329→C0139` (`max_depth 4`) → found true, highlight green, ↓ path with `T005170`/`T005171`

## Evaluation

See `docs/ML_EVALUATION.md` — honest **mule recall@25 5/25=20%** (Phase 2 graph boosted normal hubs, C0073 top), ML top5 are mules, labels never training, final ≠ fraud. Preserved strength.

## API Docs

`docs/API.md` — all 8 endpoints (`health`, `stats`, `accounts`, `:id`, `:id/transactions`, `:id/connected`, `graph/:id`, `graph/trace`), params, examples, cURL.

## Project Structure

```
MuleGuard/
  backend/src/{app,config,db,routes/*,services/*,middleware/*}
  frontend/src/{api,components,layout,pages,utils} + vite.config (manualChunks)
  ml/{generate_data,load_data,features,model,rules,graph_analysis,risk,run_pipeline}
  db/schema.sql  docs/{API,DEMO_CHECKLIST,DEMO_SCENARIO,ML_EVALUATION}
  data/synthetic (seed 42)  .env.example / frontend/.env.example
```

## Security

SQL parameterized (`$1`, `ANY`), sort whitelist `accountService.js:3`, direction whitelist, pagination bounded 1-100, depth 1-3 / trace 1-6, CORS `FRONTEND_ORIGIN`, no secrets committed, errorHandler no stack traces — see audit in Phase 5.

## Testing

```bash
python ml/run_pipeline.py && python ml/test_phase2.py  # 9 pass, 425/5184/ CRITICAL 3
node backend/tests/api.test.js  # 35 pass (30 + 5 search, plus boundary)
npm run build --prefix frontend  # split 30kB+164kB vendor lazy
# (Playwright E2E not added — prioritized backend/API, documented)
```

## License

Hackathon MVP — no auth, no PaySim (future), no deployment.
