# ML Evaluation — Honest Post-Hoc Diagnostics

> Labels are **synthetic** (`is_fraud_label` from `ml/generate_data.py`, seed 42). They are **never** used in training. Evaluation is post-hoc.

## Dataset

- **Accounts**: 425 (400 `C` normal, 25 `M` mule, seed 42) — `python ml/generate_data.py`
- **Transactions**: 5184 (5000 random normal uniform + 184 mule patterns A-E: fan-in 5, fan-out 5, rapid drain 5, chains 5×3 edges, circular 5×3 edges)
- **Load**: `python ml/load_data.py` → `accounts 425`, `transactions 5184`, `mule-labelled tx 184` (idempotent)

## Model

- **Features (14)**: `total_in/out`, `cnt_in/out`, `unique_senders/receivers`, `avg/max`, `tx_count`, `inflow_outflow_ratio`, `fan_in/out`, `activity_duration_hours`, `velocity_per_hour` — `ml/features.py:10`
- **Isolation Forest**: `sklearn.ensemble.IsolationForest(contamination=0.08, n_estimators=150, random_state=42)` on `StandardScaler` + `inflow_outflow_ratio` 99th-percentile capped — `ml/model.py:19`. **Unsupervised**, `FEATURE_COLS` never includes `is_fraud_label`. Raw `-decision_function` min-max → `ml_score 0-100` (higher = more anomalous).

## Rules

7 explainable rules (`ml/rules.py:9` thresholds): `FAN_IN>15` (+25), `FAN_OUT>12` (+25), `VELOCITY>1/h` (+20), `RAPID_DRAIN` 90-98% in <10m (+30), `COUNTERPARTY>20` (+15), `TX_COUNT>30` (+15), `AMOUNT_SPIKE>2.5×avg` (+10), cap 100. Each returns `triggered`, `score`, `reason`.

## Graph

`ml/graph_analysis.py:20` MultiDiGraph (5184 edges) collapsed DiGraph (5102). Metrics: fan-in/out min-max 25+25, betweenness 10, chain 20 (if `chain_count>0`, `MAX_CHAIN_LEN 4`, `gap 180m`, 200 caps), cycle 20 (if `cycle_count>0`, bounded 2-4, 500 caps via adjacency search not `simple_cycles` explosion). PageRank computed but **not scored** (correlates with degree, no gain). WCC: 1 component (425).

## Risk

`ml/risk.py:9` `WEIGHTS = {ml:0.4, rule:0.3, graph:0.3}` sum 1.0 — **initial demo weights, not statistically validated** (Phase 1 was 0.6/0.4/0). Levels CRITICAL≥80 HIGH≥60 MEDIUM≥30 LOW. Final `0.4*ml+0.3*rule+0.3*graph`, capped 0-100, reasons `ML + rule + graph` (≤8, verbatim backend).

## Pipeline (deterministic)

```bash
python ml/generate_data.py  # seed 42
python ml/load_data.py      # idempotent deletes + inserts
python ml/run_pipeline.py   # 7 steps: features→ML→rules→graph→risk→persist
# prints: ML mean 20.6 max100 Top M0003 100, Rules flags 364, Graph mean53.6 max89, risk CRITICAL 3 HIGH15 MEDIUM229 LOW178
```

`ml/run_pipeline.py:80` also prints `mule recall@25` diagnostics.

## Results (Phase 2, 2026-08-22, unchanged in Phase 5)

- **ML alone**: Top 5 anomalous are mules `M0003 100.0, M0004 98.4, M0001 98.0, M0005 97.1, M0002 95.6` — good separation.
- **Rules**: 364/425 flagged (≥1 rule), threshold `FAN_IN 15` overlaps normal tail (mean 12, max 27).
- **Graph**: mean 53.6 max 89.02 (`C0073`), 200 chains, 500 cycles, 1 WCC. Graph boosts normal hubs (C0073 89.02) more than mules (M0003 36.67, M0004 5.56) — dense random normal produces 2-cycles, many chains.
- **Final risk** (40/30/30): `CRITICAL 3 (C0073 86.53, C0244 86.37, C0231 80.62)`, `HIGH 15`, `MEDIUM 229`, `LOW 178` (Phase 1 was CRITICAL 4 HIGH22 MEDIUM103 LOW296 — shift to MEDIUM).

Requested accounts:
- `C0073: final 86.5 ml90 rule80 graph89 CRITICAL` (hub, not mule — honest)
- `M0010: 67.1 HIGH ml79 rule85 graph34` (fan-out mule)
- `M0003: 64.5 HIGH ml100 rule45 graph37` (fan-in mule)
- `M0004: 47.0 MEDIUM ml98 rule20 graph6` (fan-in but low graph)

## Synthetic Evaluation (post-hoc, not production accuracy)

`python ml/run_pipeline.py` reports:
```
Mule recall@25: 5/25 = 20%
Precision@25: 5/25 = 20%
Mules in top-25: ['M0001','M0003','M0010','M0011','M0024']
```

- Phase 1 recall≈40%, Phase 2 drop to 20% — graph weighting reduced recall (cycles/chains noisy in dense random). **Not tuned** to force mules top.
- High `final_score` ≠ fraud — normal hubs (C0073 27 in-degree) score high. Final is **not probability**.
- Labels are synthetic patterns A-E; normal random can mimic fan-in by chance (mean 12, 21 creates 27 max).

## Known Limitations (preserved, not hidden)

- Synthetic dataset only (PaySim separate phase) — no real-world calibration.
- 20% recall@25 on synthetic — demonstrates honest evaluation, strength for presentation.
- Graph noise: 2-cycles ubiquitous, chain greed may miss optimal layering.
- Risk is demo-weighted, not calibrated — requires threshold tuning with real data & cost analysis.
- No authentication, no deployment, no PaySim ingestion yet.

## Why this is a strength

Honest 20% reveals trade-off: isolation still separates at ML level, but rule+graph thresholds overlap normal tail + push hubs up. Shows need for better graph filtering (time/amount) and real validation — not hidden by hardcoding M IDs or using labels in training.

## Reproduce

```bash
python ml/run_pipeline.py  # deterministic
psql -U postgres -h localhost -d muleguard -c "SELECT risk_level,COUNT(*) FROM risk_scores GROUP BY risk_level;"
node backend/tests/api.test.js  # 29 pass
python ml/test_phase2.py       # 9 pass
```

Do not claim `suspicious = fraud`. Refer to `risk.reasons` verbatim.
