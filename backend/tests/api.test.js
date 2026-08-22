// Minimal API tests — run: node tests/api.test.js (requires backend running on 4000)
const BASE = process.env.API_BASE || "http://localhost:4000";
let passed = 0, failed = 0;
function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}
async function test(name, fn) {
  try { await fn(); console.log(`PASS ${name}`); passed++; }
  catch (e) { console.error(`FAIL ${name}: ${e.message}`); if (e.details) console.error(e.details); failed++; }
}
async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  const body = await res.json().catch(()=> ({}));
  return { res, body };
}

(async () => {
  await test("GET /api/health 200", async () => {
    const { res, body } = await get("/api/health");
    assert(res.status === 200, `status ${res.status}`);
    assert(body.status === "ok", "status ok");
    assert(body.database === "connected", "db connected");
  });

  await test("GET /api/accounts structure & pagination", async () => {
    const { res, body } = await get("/api/accounts?limit=5&offset=0");
    assert(res.status === 200, `status ${res.status}`);
    assert(Array.isArray(body.data), "data array");
    assert(body.pagination && body.pagination.total === 425, `total 425 got ${body.pagination.total}`);
    assert(body.data.length === 5, "limit 5");
    assert(body.data[0].final_score != null, "final_score present");
  });

  await test("GET /api/accounts sorting desc risk", async () => {
    const { body } = await get("/api/accounts?sort=risk&order=desc&limit=3");
    const scores = body.data.map(d => d.final_score);
    assert(scores[0] >= scores[1] && scores[1] >= scores[2], `not desc ${scores}`);
  });

  await test("GET /api/accounts filtering CRITICAL", async () => {
    const { body } = await get("/api/accounts?risk_level=CRITICAL&limit=10");
    assert(body.data.every(d => d.risk_level === "CRITICAL"), "all CRITICAL");
    assert(body.pagination.total === 3, `expected 3 critical got ${body.pagination.total}`);
  });

  await test("GET /api/accounts/:id detail M0003", async () => {
    const { res, body } = await get("/api/accounts/M0003");
    assert(res.status === 200, `status ${res.status}`);
    assert(body.data.account.id === "M0003", "id M0003");
    assert(body.data.risk.final_score != null, "final_score");
    assert(Array.isArray(body.data.risk.reasons) && body.data.risk.reasons.length > 0, "reasons");
    assert(body.data.features && body.data.features.total_in != null, "features");
  });

  await test("GET /api/accounts/:id 404", async () => {
    const { res } = await get("/api/accounts/DOES_NOT_EXIST");
    assert(res.status === 404, `status ${res.status}`);
  });

  await test("GET /api/accounts/:id/transactions pagination", async () => {
    const { res, body } = await get("/api/accounts/M0003/transactions?limit=3&offset=0&order=desc");
    assert(res.status === 200, `status ${res.status}`);
    assert(body.data.length === 3, "limit 3");
    assert(body.pagination.total === 18, `total 18 got ${body.pagination.total}`);
    // ordering desc
    assert(new Date(body.data[0].timestamp) >= new Date(body.data[1].timestamp), "desc order");
  });

  await test("GET /api/accounts/:id/transactions synthetic_label hidden by default", async () => {
    const { body } = await get("/api/accounts/M0003/transactions?limit=1");
    assert(!("synthetic_label" in body.data[0]) && !("is_fraud_label" in body.data[0]), "label hidden");
    const { body: b2 } = await get("/api/accounts/M0003/transactions?limit=1&include_synthetic=1");
    assert("synthetic_label" in b2.data[0], "synthetic_label when requested");
  });

  await test("GET /api/accounts/:id/connected aggregation", async () => {
    const { res, body } = await get("/api/accounts/M0003/connected");
    assert(res.status === 200, `status ${res.status}`);
    assert(body.data.account_id === "M0003", "account_id");
    assert(Array.isArray(body.data.connected), "connected array");
    assert(body.data.connected.length === 18, `expected 18 got ${body.data.connected.length}`);
    assert(body.data.connected[0].direction && body.data.connected[0].total_amount != null, "fields");
  });

  await test("GET /api/graph/:id depth=2", async () => {
    const { res, body } = await get("/api/graph/M0010?depth=2");
    assert(res.status === 200, `status ${res.status}`);
    assert(body.data.root === "M0010", "root");
    assert(body.data.nodes.length > 10, `nodes ${body.data.nodes.length}`);
    assert(body.data.edges.length > 0, "edges");
    assert(body.data.nodes.some(n => n.id === "M0010"), "root in nodes");
  });

  await test("GET /api/graph/:id depth limiting", async () => {
    const d1 = await get("/api/graph/M0010?depth=1");
    const d2 = await get("/api/graph/M0010?depth=2");
    assert(d1.body.data.nodes.length < d2.body.data.nodes.length, `depth1 ${d1.body.data.nodes.length} < depth2 ${d2.body.data.nodes.length}`);
  });

  await test("GET /api/graph/trace found", async () => {
    const { res, body } = await get("/api/graph/trace?from=M0021&to=C0139");
    assert(res.status === 200, `status ${res.status}`);
    assert(body.data.found === true, "found true");
    assert(body.data.path.length >= 2, "path len");
    assert(body.data.path[0].account_id === "M0021", "from");
    assert(body.data.path[body.data.path.length - 1].account_id === "C0139", "to");
    assert(body.data.transactions.length === body.data.path.length - 1, "tx count");
  });

  await test("GET /api/graph/trace not found", async () => {
    const { res, body } = await get("/api/graph/trace?from=M0003&to=C0001");
    assert(res.status === 200, `status ${res.status}`);
    assert(body.data.found === false, "found false");
  });

  await test("Validation invalid sort", async () => {
    const { res } = await get("/api/accounts?sort=INVALID");
    assert(res.status === 400, `status ${res.status}`);
  });

  await test("Validation invalid limit", async () => {
    const { res } = await get("/api/accounts?limit=999");
    assert(res.status === 400, `status ${res.status}`);
  });

  await test("Validation invalid risk_level", async () => {
    const { res } = await get("/api/accounts?risk_level=BAD");
    assert(res.status === 400, `status ${res.status}`);
  });

  await test("Validation invalid depth", async () => {
    const { res } = await get("/api/graph/M0010?depth=10");
    assert(res.status === 400, `status ${res.status}`);
  });

  // Phase 5 boundary tests
  await test("GET /api/stats", async () => {
    const { res, body } = await get("/api/stats");
    assert(res.status === 200, `status ${res.status}`);
    assert(body.data.total_accounts === 425, `total 425 got ${body.data.total_accounts}`);
    assert(body.data.risk_distribution.CRITICAL === 3, "critical 3");
    assert(Array.isArray(body.data.top_risk_accounts) && body.data.top_risk_accounts.length === 10, "top 10");
  });

  await test("Boundary limit=1", async () => {
    const { res, body } = await get("/api/accounts?limit=1");
    assert(res.status === 200, `status ${res.status}`);
    assert(body.data.length === 1, "len 1");
  });
  await test("Boundary limit=100", async () => {
    const { res, body } = await get("/api/accounts?limit=100");
    assert(res.status === 200, `status ${res.status}`);
    assert(body.data.length === 100, "len 100");
  });
  await test("Boundary limit=101 ->400", async () => {
    const { res } = await get("/api/accounts?limit=101");
    assert(res.status === 400, `status ${res.status}`);
  });
  await test("Boundary offset negative ->400", async () => {
    const { res } = await get("/api/accounts?offset=-1");
    assert(res.status === 400, `status ${res.status}`);
  });
  await test("Boundary depth=1", async () => {
    const { res, body } = await get("/api/graph/M0010?depth=1");
    assert(res.status === 200, `status ${res.status}`);
    assert(body.data.depth === 1, "depth 1");
  });
  await test("Boundary depth=3", async () => {
    const { res, body } = await get("/api/graph/M0010?depth=3");
    assert(res.status === 200, `status ${res.status}`);
    assert(body.data.depth === 3, "depth 3");
  });
  await test("Boundary depth=4 ->400", async () => {
    const { res } = await get("/api/graph/M0010?depth=4");
    assert(res.status === 400, `status ${res.status}`);
  });
  await test("Boundary trace max_depth=6", async () => {
    const { res } = await get("/api/graph/trace?from=M0021&to=C0139&max_depth=6");
    assert(res.status === 200, `status ${res.status}`);
  });
  await test("Boundary trace max_depth=7 ->400", async () => {
    const { res } = await get("/api/graph/trace?from=M0021&to=C0139&max_depth=7");
    assert(res.status === 400, `status ${res.status}`);
  });
  await test("Validation invalid order", async () => {
    const { res } = await get("/api/accounts?order=INVALID");
    assert(res.status === 400, `status ${res.status}`);
  });
  await test("Unknown route 404", async () => {
    const { res } = await get("/api/unknown_route_xyz");
    assert(res.status === 404, `status ${res.status}`);
  });
  await test("Malformed account ID 404", async () => {
    const { res } = await get("/api/accounts/%20%20%20");
    assert(res.status === 404, `status ${res.status}`);
  });

  // Phase 6 search tests
  await test("Search q=M0003 finds M0003", async () => {
    const { res, body } = await get("/api/accounts?q=M0003");
    assert(res.status === 200, `status ${res.status}`);
    assert(body.data.length >= 1, "found at least 1");
    assert(body.data.some(d => d.account_id === "M0003"), "contains M0003");
  });
  await test("Search nonexistent q empty", async () => {
    const { res, body } = await get("/api/accounts?q=ZZZ_NOPE_999");
    assert(res.status === 200, `status ${res.status}`);
    assert(body.data.length === 0, "empty");
    assert(body.pagination.total === 0, "total 0");
  });
  await test("Search with filter q + risk_level", async () => {
    const { res, body } = await get("/api/accounts?q=M000&risk_level=HIGH");
    assert(res.status === 200, `status ${res.status}`);
    assert(body.data.every(d => d.account_id.includes("M000") && d.risk_level === "HIGH"), "filter+q");
  });
  await test("Search malicious q parameterized", async () => {
    const { res, body } = await get("/api/accounts?q=%27%20OR%20%271%27=%271");
    assert(res.status === 200, `status ${res.status}`);
    // should not return all 425 nor error — parameterized
    assert(body.pagination.total < 425, "not all");
  });
  await test("Search case-insensitive q=m0003", async () => {
    const { res, body } = await get("/api/accounts?q=m0003");
    assert(res.status === 200, `status ${res.status}`);
    assert(body.data.some(d => d.account_id === "M0003"), "case-insensitive");
  });

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
})();
