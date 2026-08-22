# MuleGuard Demo Checklist

Deterministic demo — seed 42. Run before every demo.

## 1. Start PostgreSQL

```bash
psql -U postgres -h localhost -c "SELECT version();"
# expect PostgreSQL 18.x
psql -U postgres -h localhost -d muleguard -c "SELECT COUNT(*) FROM accounts;"
# expect 425 (if 0, regenerate)
```

If DB missing:
```bash
psql -U postgres -h localhost -d postgres -c "CREATE DATABASE muleguard;"
psql -U postgres -h localhost -d muleguard -f db/schema.sql
```

## 2. Generate data (deterministic, seed 42)

```bash
python ml/generate_data.py
# expect: Accounts generated: 425 (normal 400, mule 25)
#         Transactions generated: 5184 (normal~5000, mule_patterns=184)
#         Wrote data/synthetic/accounts.csv
#         Wrote data/synthetic/transactions.csv
```

## 3. Load data (idempotent)

```bash
python ml/load_data.py
# expect: Accounts loaded: 425
#         Transactions loaded: 5184 (mule-labelled tx: 184)
#         Synthetic mule accounts: 25
#         Total accounts in DB: 425
#         Total transactions in DB: 5184
```

## 4. Run ML pipeline (deterministic, contamination 0.08)

```bash
python ml/run_pipeline.py
# expect: Features 425, ML mean ~20.6 max 100, Rule flags 364
#         Graph: 425 nodes, 5184 multi-edges, 5102 collapsed, WCC 1, chains 200, cycles 500
#         Weights ML 40% + Rules 30% + Graph 30%
#         Risk levels: CRITICAL 3, HIGH 15, MEDIUM 229, LOW 178 (stable)
#         Top: C0073 86.5, C0244 86.4 (honest — normal hubs can be top)
#         Mule recall@25 = 5/25 = 20% (do not hide)
```

## 5. Start backend

```bash
npm run dev --prefix backend
# expect: MuleGuard backend listening on http://localhost:4000
curl http://localhost:4000/api/health
# expect: {"status":"ok","database":"connected"}

curl http://localhost:4000/api/stats
# expect: total_accounts 425, risk_distribution {LOW:178,...}

node backend/tests/api.test.js
# expect: 35 passed, 0 failed (30 + 5 search: q=M0003, nonexistent, filter+q, malicious, case-insensitive)
```

## 6. Start frontend

```bash
npm run dev --prefix frontend
# expect: vite v6.4.3, Local http://localhost:5173/
curl http://localhost:5173/ | grep -q "MuleGuard"
```

## 7. Verify workflow (browser at http://localhost:5173)

- [ ] **Dashboard** `/` — KPIs Total 425, CRITICAL 3, HIGH 15, etc. Top Risk Accounts table shows C0073/C0244, pie distribution.
- [ ] **Accounts** `/accounts` — table 425 total, sort by Final/ML/Rules/Graph works, filter `CRITICAL` shows 3, pagination Prev/Next.
- [ ] **Search** — type `M0003` in search box (debounced 300ms) → 1 result `M0003` via `GET /api/accounts?q=M0003` (ILIKE parameterized); try `m0003` case-insensitive, `ZZZ` → 0.
- [ ] **CRITICAL filter** — click CRITICAL badge → only 3 rows; with search `M000` + filter `HIGH` → filtered.
- [ ] **M0003** `/accounts/M0003` — HIGH 64.5, ml 100, rule 45, graph 36.67, reasons include `High anomaly score (100/100)`, `High fan-in: 18`, `Participates in a 3-account chain`.
  - Features: Total In ₹31,281 etc.
  - Transactions: 18 total, Incoming vs Outgoing distinguished.
  - Connected: 18 counterparties, click one → navigates.
- [ ] **Why Flagged?** — ExplanationPanel shows backend `risk.reasons` verbatim, not frontend-generated.
- [ ] **Transactions** — pagination works, **Newest/Oldest toggle** (`order=desc` vs `asc`, chronological layering), no synthetic_label shown unless `include_synthetic=1`.
- [ ] **Connected Accounts** — direction incoming/outgoing, totals.
- [ ] **Graph M0010** `/graph/M0010` — default depth 2 → 243 nodes / 363 edges, depth 1 →15 nodes, depth 3 →423 nodes, deterministic positions (final_score DESC→id ASC, 1→2→1 returns same), root highlighted, risk colors, arrow = money flow.
- [ ] **Graph M0021** `/graph/M0021` — depth 2 shows 48 nodes (includes C0329, C0139), cycles present, depth toggle stable.
- [ ] **Trace M0021 → C0139** — form FROM `M0021` TO `C0139` → Trace → found true path `M0021 → C0329 → C0139` txs `T005170 (₹11,778)` `T005171 (₹11,618)`, highlighted green.
- [ ] **No path** `M0003 → C0001` → `No directed money-flow path found within the selected depth.` (not error).
- [ ] **Graph legend** — LOW/MEDIUM/HIGH/CRITICAL + Arrow direction explained.
- [ ] **Error state** — stop backend, refresh Dashboard → `Unable to connect to MuleGuard API. Is the backend running...` (not TypeError).
- [ ] **Empty/404** — `/accounts/DOES_NOT_EXIST` → 404 page.

## 8. Build check

```bash
npm run build --prefix frontend
# expect: initial 30.42kB + vendor 164kB + reactflow 131kB lazy + recharts 344kB lazy split (was 677kB monolith)
python ml/test_phase2.py
# expect: 9 passed
```

If any step fails, see `docs/ML_EVALUATION.md` for known limitations and `docs/DEMO_SCENARIO.md` for investigator narrative.
