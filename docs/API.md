# MuleGuard API

Base URL: `http://localhost:4000`

All success responses are JSON. Collections include `pagination` where applicable. Errors are `{ error: "...", details?: ... }` — never leak SQL, credentials, or stack traces.

## Health

### GET /api/health

Checks API + PostgreSQL connectivity. Does NOT claim ML model loaded (batch pipeline).

**Response 200**
```json
{ "status": "ok", "database": "connected", "timestamp": "2026-08-22T07:07:53.978Z" }
```

**500** if DB disconnected.

---

## Stats

### GET /api/stats

Lightweight aggregate for Dashboard (avoids 5 separate calls). All values from PostgreSQL via `COUNT(*)`, `GROUP BY risk_level`, `ORDER BY final_score DESC LIMIT 10`.

**Response 200**
```json
{
  "data": {
    "total_accounts": 425,
    "risk_distribution": { "LOW": 178, "MEDIUM": 229, "HIGH": 15, "CRITICAL": 3 },
    "top_risk_accounts": [
      { "account_id": "C0073", "name": "Account C0073", "final_score": 86.53, "risk_level": "CRITICAL", "ml_score": 89.57, "rule_score": 80, "graph_score": 89.02, "reasons": ["..."] }
    ]
  }
}
```

**500** on DB failure.

---

## Accounts

### GET /api/accounts

List accounts with risk scores (joined `accounts` + `risk_scores`).

**Query params**
| param | type | default | constraints | description |
|---|---|---|---|---|
| q | string | — | 1-50 chars, optional | Search by account ID or name (ILIKE `%q%`, parameterized, case-insensitive, prefix/contains) |
| sort | string | risk | whitelist: risk, ml_score, rule_score, graph_score, account_id, final_score | `risk` maps to `final_score` |
| order | string | desc | asc/desc | sort direction |
| risk_level | string | — | LOW/MEDIUM/HIGH/CRITICAL | filter |
| limit | int | 50 | 1-100 | pagination |
| offset | int | 0 | >=0 | pagination |

**Success 200**
```json
{
  "data": [
    {
      "account_id": "C0073",
      "name": "Account C0073",
      "type": "personal",
      "created_at": "2026-01-21T00:00:00.000Z",
      "final_score": 86.53,
      "risk_level": "CRITICAL",
      "ml_score": 89.57,
      "rule_score": 80,
      "graph_score": 89.02,
      "reasons": ["High anomaly score (90/100) ...", "High fan-in: 27 ..."]
    }
  ],
  "pagination": { "limit": 50, "offset": 0, "total": 425 }
}
```

**400** invalid sort/order/risk_level/limit/offset.

---

### GET /api/accounts/:id

Full investigator summary.

**Path:** `id` — account ID (e.g. `M0003`)

**Response 200**
```json
{
  "data": {
    "account": { "id": "M0003", "name": "Mule M0003", "type": "personal", "created_at": "..." },
    "risk": { "final_score": 64.5, "risk_level": "HIGH", "ml_score": 100, "rule_score": 45, "graph_score": 36.67, "reasons": ["High anomaly score ..."] },
    "features": { "total_in": 31281.81, "total_out": 0, "cnt_in": 18, "cnt_out": 0, "unique_senders": 18, "unique_receivers": 0, "avg_amount": 1737.88, "max_amount": 2918.32, "tx_count": 18, "inflow_outflow_ratio": 31281.81, "fan_in_score": 18, "fan_out_score": 0, "activity_duration_hours": 1.87, "velocity_per_hour": 9.6429 }
  }
}
```

**404** if account not found.

---

### GET /api/accounts/:id/transactions

Paginated transactions where account is sender or receiver, ordered by timestamp.

**Query params**
| param | default | constraints |
|---|---|---|
| limit | 50 | 1-100 |
| offset | 0 | >=0 |
| order | desc | asc/desc (by timestamp) |
| include_synthetic | false | 1/true to expose `synthetic_label` (is_fraud_label) for evaluation; hidden by default |

**Response 200**
```json
{
  "data": [
    { "id": "T005034", "from_account": "C0126", "to_account": "M0003", "amount": 800.54, "timestamp": "2026-01-20T01:57:00.000Z", "type": "TRANSFER" }
  ],
  "pagination": { "limit": 3, "offset": 0, "total": 18 }
}
```
If `include_synthetic=1`, each item adds `synthetic_label: 0|1` — marked as evaluation-only, not a production fraud indicator.

**404** if account not found. **400** invalid limit/offset/order.

---

### GET /api/accounts/:id/connected

Direct counterparties aggregated.

**Response 200**
```json
{
  "data": {
    "account_id": "M0003",
    "connected": [
      { "account_id": "C0148", "direction": "incoming", "transaction_count": 1, "total_amount": 2918.32, "first_seen": "...", "last_seen": "..." }
    ]
  }
}
```
`direction` is `incoming` (them→you) or `outgoing` (you→them). Aggregated, not per-transaction.

**404** if account not found.

---

## Graph

### GET /api/graph/:id?depth=2

Bounded ego-graph for React Flow. Traversal from root out to `depth` hops (both directions), collapsed edges.

**Query params**
| param | default | constraints |
|---|---|---|
| depth | 2 | 1-3 |

**Response 200**
```json
{
  "data": {
    "root": "M0010",
    "depth": 2,
    "nodes": [ { "id": "M0010", "label": "Mule M0010", "risk_level": "HIGH", "final_score": 67.13 } ],
    "edges": [ { "source": "M0010", "target": "C0062", "transaction_count": 1, "total_amount": 1876.83, "first_seen": "...", "last_seen": "..." } ]
  }
}
```
Direction of money preserved (`source → target`).

**404** if root not found. **400** invalid depth.

---

### GET /api/graph/trace?from=A&to=B&max_depth=4

Directed money-flow path (BFS) between two accounts.

**Query params**
| param | required | default | constraints |
|---|---|---|---|
| from | yes | — | existing account ID |
| to | yes | — | existing account ID |
| max_depth | no | 4 | 1-6 |

**Response 200 (found)**
```json
{
  "data": { "from": "M0021", "to": "C0139", "found": true, "path": [{ "account_id": "M0021" }, { "account_id": "C0329" }, { "account_id": "C0139" }], "transactions": [ { "id": "T005170", "from_account": "M0021", "to_account": "C0329", "amount": 11778.01, "timestamp": "..." }, { "id": "T005171", "from_account": "C0329", "to_account": "C0139", "amount": 11618.9, "timestamp": "..." } ] }
}
```

**Response 200 (not found)**
```json
{ "data": { "from": "M0003", "to": "C0001", "found": false, "path": [], "transactions": [] } }
```

**404** if `from` or `to` account does not exist. **400** missing params or invalid `max_depth`.

---

## Validation & Errors

- 400 for invalid `limit/offset/sort/order/risk_level/depth/max_depth` or missing required params.
- 404 for account/path not found.
- 500 for DB failure (never leaks SQL).

All DB access uses parameterized queries (`$1`, `ANY($1)`), never interpolates user input.

## CORS

`FRONTEND_ORIGIN` env (default `http://localhost:5173`) — `cors({ origin: config.frontendOrigin })`.

## Environment

- `DATABASE_URL` — PostgreSQL connection string
- `BACKEND_PORT` / `PORT` — default 4000
- `FRONTEND_ORIGIN` — Vite origin

## Example cURL

```bash
curl http://localhost:4000/api/health
curl http://localhost:4000/api/stats
curl "http://localhost:4000/api/accounts?sort=risk&order=desc&limit=5"
curl "http://localhost:4000/api/accounts?q=M0003"
curl http://localhost:4000/api/accounts/M0003
curl "http://localhost:4000/api/accounts/M0003/transactions?limit=3&order=desc"
curl "http://localhost:4000/api/accounts/M0003/transactions?limit=3&order=asc"
curl http://localhost:4000/api/accounts/M0003/connected
curl "http://localhost:4000/api/graph/M0010?depth=2"
curl "http://localhost:4000/api/graph/trace?from=M0021&to=C0139"
```
