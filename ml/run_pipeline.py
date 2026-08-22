"""
MuleGuard single-command pipeline:
  features -> IsolationForest -> rules -> graph -> risk -> DB
  Phase 2 adds graph intelligence (NetworkX MultiDiGraph).
"""
import os
import json
from pathlib import Path
import psycopg
from dotenv import load_dotenv
from features import extract_features_from_db, save_features
from model import score_accounts
from rules import evaluate_rules
from graph_analysis import analyze_graph
from risk import combine_scores, WEIGHTS

load_dotenv()
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/muleguard")

def run():
    print("="*60)
    print("MuleGuard pipeline")
    print("="*60)

    # 1. Features
    print("\n[1/5] Extracting features...")
    df = extract_features_from_db()
    print(f"  Accounts analyzed: {len(df)}")
    save_features(df, to_db=True)

    # 2. ML
    print("\n[2/5] Running Isolation Forest (contamination=0.08)...")
    ml_scores = score_accounts(df)
    print(f"  ML scores computed. Mean={ml_scores.ml_score.mean():.1f}, max={ml_scores.ml_score.max():.1f}")
    print("  Top 5 anomalous:")
    for _, r in ml_scores.sort_values("ml_score", ascending=False).head(5).iterrows():
        print(f"    {r.account_id}: {r.ml_score:.1f}")

    # 3. Rules
    print("\n[3/5] Evaluating behavioral rules...")
    rule_out = evaluate_rules(df)
    print(f"  Rule scores computed. Accounts with flags: {(rule_out.rule_score>0).sum()}")

    # 4. Graph
    print("\n[4/7] Building transaction graph (MultiDiGraph)...")
    graph_df, stats, _ = analyze_graph()
    print(f"  Graph: {stats['nodes']} nodes, {stats['edges_multi']} tx-edges, {stats['edges_collapsed']} collapsed")
    print(f"  WCC: {stats['wcc_count']} components (largest {stats['wcc_largest']})")
    print(f"  Chains detected: {len(stats['chains'])} (time-ordered, max gap 180m)")
    print(f"  Cycles detected (2-4, capped 500): {len(stats['cycles'])}")
    print(f"  Top betweenness: {stats['betweenness_top'][:3]}")
    print(f"  Top graph_score: {graph_df.sort_values('graph_score', ascending=False).head(3)[['account_id','graph_score']].to_dict(orient='records')}")
    print(f"  Graph score mean {graph_df.graph_score.mean():.1f} max {graph_df.graph_score.max():.1f}")

    # 5. Risk
    print(f"\n[5/7] Combining risk (ML {WEIGHTS['ml']*100:.0f}% + Rules {WEIGHTS['rule']*100:.0f}% + Graph {WEIGHTS['graph']*100:.0f}%)...")
    risk_df = combine_scores(ml_scores, rule_out, graph_df)
    print("  Distribution:")
    print(risk_df["risk_level"].value_counts().to_string())

    # 6. Persist
    print("\n[6/7] Persisting risk_scores...")
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM risk_scores")
            for _, r in risk_df.iterrows():
                cur.execute("""
                    INSERT INTO risk_scores (account_id, ml_score, rule_score, graph_score, final_score, risk_level, reasons)
                    VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
                """, (r.account_id, float(r.ml_score), float(r.rule_score), float(r.graph_score), float(r.final_score), r.risk_level, json.dumps(r.reasons)))
        conn.commit()
    print(f"  Persisted {len(risk_df)} risk scores.")

    # Summary + evaluation (synthetic labels for diagnostics only, never training)
    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM accounts")
            print(f"Accounts: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM transactions")
            print(f"Transactions: {cur.fetchone()[0]}")
            cur.execute("SELECT id FROM accounts WHERE id LIKE 'M%%'")
            mule_ids = {r[0] for r in cur.fetchall()}
    print(f"Accounts analyzed: {len(risk_df)}")
    print(f"Graph stats: chains {len(stats['chains'])}, cycles {len(stats['cycles'])}, wcc {stats['wcc_count']}")
    print("Highest-risk accounts (final = ml+rule+graph):")
    for _, r in risk_df.sort_values("final_score", ascending=False).head(10).iterrows():
        is_m = "MULE" if r.account_id in mule_ids else "     "
        print(f"  {r.account_id} {is_m} | final={r.final_score:.1f} ({r.risk_level}) | ml={r.ml_score:.0f} rule={r.rule_score:.0f} graph={r.graph_score:.0f} | {r.reasons[0][:85]}")
    print("\nRisk level distribution:")
    print(risk_df["risk_level"].value_counts().to_string())
    # synthetic evaluation
    top_k = 25
    top_ids = set(risk_df.sort_values("final_score", ascending=False).head(top_k)["account_id"])
    tp = len(top_ids & mule_ids)
    print(f"\nSynthetic evaluation (top-{top_k}, labels NEVER used in training):")
    print(f"  Mule recall@{top_k}: {tp}/25 = {tp/25*100:.0f}%")
    print(f"  Precision@{top_k}: {tp}/{top_k} = {tp/top_k*100:.0f}%")
    if tp > 0:
        print(f"  Mules in top-{top_k}: {sorted(top_ids & mule_ids)}")
    # inspect requested accounts
    for aid in ["C0073","M0010","M0003","M0004"]:
        row = risk_df[risk_df.account_id==aid]
        if not row.empty:
            r=row.iloc[0]
            print(f"  {aid}: final={r.final_score:.1f} ml={r.ml_score:.0f} rule={r.rule_score:.0f} graph={r.graph_score:.0f} level={r.risk_level}")
    print("\nPipeline complete. Data in PostgreSQL: account_features + risk_scores (graph_score real)")
    print("Weights:", WEIGHTS, "- initial demo weights, not statistically validated.")

if __name__ == "__main__":
    run()
