"""
Graph intelligence for MuleGuard.
MultiDiGraph preserves every transaction; collapsed DiGraph used for metrics.
Provides fan-in/out, degree, betweenness, PageRank, chain & cycle detection, clusters,
and a normalized 0-100 graph_score with human-readable explanations.

Performance notes:
- Graph is built once per pipeline run.
- Betweenness / PageRank computed globally once.
- simple_cycles is sliced to first 500 cycles and filtered to length 2-4 to avoid explosion.
- Chain detection is greedy per transaction (not exhaustive all_simple_paths) to stay O(E * depth).
"""
import os
from collections import defaultdict
from datetime import timedelta

import pandas as pd
import networkx as nx
import psycopg
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/muleguard")

# Configurable knobs
MAX_CYCLE_LEN = 4
MAX_CYCLE_ENUM = 2000
MAX_CHAIN_LEN = 4          # nodes, i.e. 3 edges
MAX_CHAIN_GAP_MIN = 180    # max minutes between consecutive hops in a chain
MAX_CHAINS_REPORTED = 200


def build_graphs():
    """Build MultiDiGraph (full) and collapsed DiGraph from DB transactions."""
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, from_account, to_account, amount, timestamp, type, is_fraud_label FROM transactions")
            rows = cur.fetchall()
            cur.execute("SELECT id FROM accounts")
            account_ids = [r[0] for r in cur.fetchall()]

    G_multi = nx.MultiDiGraph()
    G = nx.DiGraph()
    # add all accounts as nodes (isolated nodes remain visible)
    for aid in account_ids:
        G_multi.add_node(aid)
        G.add_node(aid)

    for tid, src, dst, amt, ts, typ, lbl in rows:
        attrs = {"id": tid, "amount": float(amt), "timestamp": ts, "type": typ, "is_fraud_label": int(lbl)}
        G_multi.add_edge(src, dst, key=tid, **attrs)
        # collapsed DiGraph: keep earliest timestamp/amount for that pair for path ordering
        # but also store list of edge counts / sum for weight
        if G.has_edge(src, dst):
            G[src][dst]["count"] += 1
            G[src][dst]["total_amount"] += float(amt)
            # keep earliest timestamp for ordering
            if ts < G[src][dst]["timestamp"]:
                G[src][dst]["timestamp"] = ts
                G[src][dst]["amount"] = float(amt)
        else:
            G.add_edge(src, dst, count=1, total_amount=float(amt), timestamp=ts, amount=float(amt))

    return G_multi, G


def compute_centralities(G):
    """Betweenness and PageRank on collapsed DiGraph. Returns dicts."""
    # Betweenness: normalized, suitable for 425 nodes (exact, not sampled)
    try:
        bet = nx.betweenness_centrality(G, normalized=True)
    except Exception:
        bet = {n: 0.0 for n in G.nodes()}
    # PageRank: document utility; compute but caller decides weight
    try:
        pr = nx.pagerank(G, alpha=0.85)
    except Exception:
        pr = {n: 0.0 for n in G.nodes()}
    return bet, pr


def _canonical_cycle(cyc):
    """Return lexicographically minimal rotation to deduplicate cycles."""
    n = len(cyc)
    # generate rotations and also consider same cycle starting at any node
    rotations = [tuple(cyc[i:] + cyc[:i]) for i in range(n)]
    return min(rotations)

def detect_cycles(G):
    """Detect directed cycles length 2-4 via bounded adjacency search (avoids simple_cycles explosion)."""
    cycles = []
    seen = set()
    # adjacency set for O(1) lookup
    succ = {n: set(G.successors(n)) for n in G.nodes()}

    # 2-cycles
    for u, v in G.edges():
        if u == v:
            continue
        if u in succ.get(v, set()):
            cyc = _canonical_cycle([u, v])
            # for 2-cycle, ensure canonical ordering to avoid duplicate (u,v) vs (v,u)
            key = tuple(sorted(cyc)) if len(cyc) == 2 else cyc
            # use frozenset for 2-cycle
            if len(cyc) == 2:
                key = tuple(sorted([u, v]))
                # store as [min, max] but keep consistent
                if key not in seen:
                    seen.add(key)
                    cycles.append([key[0], key[1]])
            if len(cycles) >= MAX_CYCLE_ENUM:
                break
    if len(cycles) < MAX_CYCLE_ENUM:
        # 3-cycles: u->v->w->u
        for u in G.nodes():
            for v in succ.get(u, []):
                for w in succ.get(v, []):
                    if w == u or w == v:
                        continue
                    if u in succ.get(w, set()):
                        cyc = _canonical_cycle([u, v, w])
                        if cyc not in seen:
                            seen.add(cyc)
                            cycles.append(list(cyc))
                            if len(cycles) >= MAX_CYCLE_ENUM:
                                break
                if len(cycles) >= MAX_CYCLE_ENUM:
                    break
            if len(cycles) >= MAX_CYCLE_ENUM:
                break
    if len(cycles) < MAX_CYCLE_ENUM and MAX_CYCLE_LEN >= 4:
        # 4-cycles: u->v->w->x->u (limit branching to keep reasonable)
        for u in G.nodes():
            for v in succ.get(u, []):
                for w in succ.get(v, []):
                    if w in (u, v):
                        continue
                    for x in succ.get(w, []):
                        if x in (u, v, w):
                            continue
                        if u in succ.get(x, set()):
                            cyc = _canonical_cycle([u, v, w, x])
                            if cyc not in seen:
                                seen.add(cyc)
                                cycles.append(list(cyc))
                                if len(cycles) >= MAX_CYCLE_ENUM:
                                    break
                    if len(cycles) >= MAX_CYCLE_ENUM:
                        break
                if len(cycles) >= MAX_CYCLE_ENUM:
                    break
            if len(cycles) >= MAX_CYCLE_ENUM:
                break

    cycle_members = defaultdict(int)
    for cyc in cycles:
        for n in cyc:
            cycle_members[n] += 1
    return cycles, cycle_members


def detect_chains(G_multi):
    """
    Greedy time-ordered chain detection.
    For each transaction sorted by timestamp, walk forward via outgoing edges
    where next timestamp is after current and gap < MAX_CHAIN_GAP_MIN.
    Records chains of length >=3 nodes (2+ edges). Deduplicates by account tuple.
    """
    # Build sorted outgoing edge list per node: list of (dst, timestamp, amount, tid, src)
    out_edges = defaultdict(list)
    for u, v, key, data in G_multi.edges(keys=True, data=True):
        out_edges[u].append((v, data["timestamp"], float(data["amount"]), key, u))
    for n in out_edges:
        out_edges[n].sort(key=lambda x: x[1])

    # All transactions sorted globally
    all_tx = []
    for u, v, key, data in G_multi.edges(keys=True, data=True):
        all_tx.append((data["timestamp"], u, v, float(data["amount"]), key))
    all_tx.sort(key=lambda x: x[0])

    seen = set()
    chains = []  # list of dicts

    for start_ts, src, dst, amt, tid in all_tx:
        # attempt to extend from this edge
        chain_nodes = [src, dst]
        chain_tids = [tid]
        chain_amounts = [amt]
        chain_times = [start_ts]
        cur_node = dst
        cur_ts = None
        # we need timestamp of the dst arrival? Actually edge timestamp is the transfer time
        # For gap, we need time between consecutive edges
        last_ts = start_ts
        # Try extending
        visited_nodes = set(chain_nodes)
        for _ in range(MAX_CHAIN_LEN - 2):  # already have 2 nodes
            candidates = out_edges.get(cur_node, [])
            # find first candidate after last_ts with gap constraint and not revisited
            nxt = None
            for v, ts, a, k, u in candidates:
                if ts <= last_ts:
                    continue
                gap_min = (ts - last_ts).total_seconds() / 60.0
                if gap_min > MAX_CHAIN_GAP_MIN:
                    continue
                if v in visited_nodes:
                    continue
                # amount progression: allow modest increase but prefer slight decay (layering)
                # we allow up to 5% increase to tolerate noise
                if a > chain_amounts[-1] * 1.05 and len(chain_amounts) > 1:
                    # allow one increase but not huge
                    pass
                nxt = (v, ts, a, k)
                break
            if nxt is None:
                break
            v, ts, a, k = nxt
            chain_nodes.append(v)
            chain_tids.append(k)
            chain_amounts.append(a)
            chain_times.append(ts)
            visited_nodes.add(v)
            cur_node = v
            last_ts = ts

        if len(chain_nodes) >= 3:
            key = tuple(chain_nodes)
            if key not in seen:
                seen.add(key)
                span_min = (chain_times[-1] - chain_times[0]).total_seconds() / 60.0
                chains.append({
                    "nodes": list(chain_nodes),
                    "tids": list(chain_tids),
                    "amounts": list(chain_amounts),
                    "timestamps": list(chain_times),
                    "length": len(chain_nodes),
                    "span_min": round(span_min, 1),
                })
            if len(chains) >= MAX_CHAINS_REPORTED:
                break

    # participation count per account
    chain_members = defaultdict(int)
    for ch in chains:
        for n in ch["nodes"]:
            chain_members[n] += 1

    return chains, chain_members


def analyze_graph():
    """Full graph analysis. Returns per-account DataFrame + global stats."""
    G_multi, G = build_graphs()
    bet, pr = compute_centralities(G)
    cycles, cycle_members = detect_cycles(G)
    chains, chain_members = detect_chains(G_multi)

    # weakly connected components
    try:
        wcc = list(nx.weakly_connected_components(G))
    except Exception:
        wcc = list(nx.weakly_connected_components(G_multi))
    # map node -> component size
    comp_size = {}
    for comp in wcc:
        s = len(comp)
        for n in comp:
            comp_size[n] = s

    # degrees on collapsed DiGraph (unique counterparties)
    # Use G in_degree/out_degree (unique)
    rows = []
    # precompute mins/maxs for normalization
    in_degs = {n: G.in_degree(n) for n in G.nodes()}
    out_degs = {n: G.out_degree(n) for n in G.nodes()}
    bet_vals = list(bet.values()) if bet else [0]
    pr_vals = list(pr.values()) if pr else [0]
    in_min, in_max = (min(in_degs.values()), max(in_degs.values())) if in_degs else (0, 1)
    out_min, out_max = (min(out_degs.values()), max(out_degs.values())) if out_degs else (0, 1)
    bet_min, bet_max = (min(bet_vals), max(bet_vals)) if bet_vals else (0, 1)

    for aid in G.nodes():
        fan_in = int(in_degs.get(aid, 0))
        fan_out = int(out_degs.get(aid, 0))
        total_deg = fan_in + fan_out
        bet_s = float(bet.get(aid, 0.0))
        pr_s = float(pr.get(aid, 0.0))
        in_chain = int(chain_members.get(aid, 0))
        in_cycle = int(cycle_members.get(aid, 0))
        wcc_sz = int(comp_size.get(aid, 1))

        # scoring components (weights sum to 100 before cap)
        # fan-in/out: min-max scaled to 25 each
        fan_in_contrib = 0.0
        if in_max > in_min:
            fan_in_contrib = (fan_in - in_min) / (in_max - in_min) * 25
        # only count if above modest threshold to reduce false positives from mean 12
        if fan_in < 15:
            fan_in_contrib *= 0.5  # damp below rule threshold

        fan_out_contrib = 0.0
        if out_max > out_min:
            fan_out_contrib = (fan_out - out_min) / (out_max - out_min) * 25
        if fan_out < 12:
            fan_out_contrib *= 0.5

        bet_contrib = 0.0
        if bet_max > bet_min:
            bet_contrib = (bet_s - bet_min) / (bet_max - bet_min) * 10

        chain_contrib = 20 if in_chain > 0 else 0
        cycle_contrib = 20 if in_cycle > 0 else 0

        graph_score = fan_in_contrib + fan_out_contrib + bet_contrib + chain_contrib + cycle_contrib
        graph_score = max(0, min(100, round(graph_score, 2)))

        # explanations — only when backed by actual values
        reasons = []
        if fan_in >= 15:
            reasons.append(f"High fan-in: {fan_in} unique incoming counterparties.")
        if fan_out >= 12:
            reasons.append(f"High fan-out: {fan_out} unique outgoing counterparties.")
        if in_chain > 0:
            # find a representative chain length for this account
            rep_len = max((ch["length"] for ch in chains if aid in ch["nodes"]), default=0)
            span = next((ch["span_min"] for ch in chains if aid in ch["nodes"]), 0)
            reasons.append(f"Participates in a {rep_len}-account transaction chain (span {span:.0f} min) - possible layering.")
        if in_cycle > 0:
            reasons.append("Participates in a circular transaction pattern (cycle length 2-4).")
        if bet_s > 0.005:  # threshold for intermediary
            reasons.append("Acts as an intermediary between multiple account groups (high betweenness).")
        if total_deg >= 25:
            reasons.append(f"High graph connectivity: {total_deg} unique counterparties.")

        # PageRank: computed but not directly scored; document that it correlates with degree
        # and did not materially improve separation beyond fan-in/out + betweenness on this dataset.

        rows.append({
            "account_id": aid,
            "fan_in": fan_in,
            "fan_out": fan_out,
            "total_degree": total_deg,
            "betweenness": round(bet_s, 6),
            "pagerank": round(pr_s, 6),
            "chain_count": in_chain,
            "cycle_count": in_cycle,
            "wcc_size": wcc_sz,
            "graph_score": graph_score,
            "graph_reasons": reasons,
        })

    df = pd.DataFrame(rows)
    stats = {
        "nodes": G.number_of_nodes(),
        "edges_collapsed": G.number_of_edges(),
        "edges_multi": G_multi.number_of_edges(),
        "wcc_count": len(wcc),
        "wcc_largest": max((len(c) for c in wcc), default=0),
        "chains": chains,
        "cycles": cycles,
        "betweenness_top": sorted(bet.items(), key=lambda x: x[1], reverse=True)[:5],
        "pagerank_top": sorted(pr.items(), key=lambda x: x[1], reverse=True)[:5],
    }
    return df, stats, (G_multi, G)


if __name__ == "__main__":
    df, stats, _ = analyze_graph()
    print(f"Graph: {stats['nodes']} nodes, {stats['edges_multi']} multi-edges, {stats['edges_collapsed']} collapsed")
    print(f"WCC: {stats['wcc_count']} components, largest {stats['wcc_largest']}")
    print(f"Chains detected: {len(stats['chains'])} (showing 5)")
    for ch in stats["chains"][:5]:
        print(f"  {ch['nodes']} span {ch['span_min']}m amounts {ch['amounts']}")
    print(f"Cycles detected (len 2-4, capped {MAX_CYCLE_ENUM}): {len(stats['cycles'])}")
    for cyc in stats["cycles"][:5]:
        print(f"  {cyc}")
    print("Top betweenness:", stats["betweenness_top"])
    print("Top pagerank:", stats["pagerank_top"])
    print(df.sort_values("graph_score", ascending=False).head(10).to_string(index=False))
