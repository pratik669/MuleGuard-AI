"""
Risk engine - combines ML + Rules + Graph into explainable risk score.
Phase 2: ML 40% + Rules 30% + Graph 30% (initial demo weights, not statistically validated).
Graph score reflects fan-in/out, chains, cycles, centrality. See graph_analysis.py.
"""
import pandas as pd
import json

WEIGHTS = {"ml": 0.4, "rule": 0.3, "graph": 0.3}  # sum 1.0, configurable
LEVELS = [(80,"CRITICAL"), (60,"HIGH"), (30,"MEDIUM"), (0,"LOW")]

def classify(score):
    for thresh, lvl in LEVELS:
        if score >= thresh:
            return lvl
    return "LOW"

def combine_scores(ml_df, rule_df, graph_df=None, graph_score_default=0):
    """
    ml_df: account_id, ml_score
    rule_df: account_id, rule_score, triggered_rules, reasons
    graph_df: account_id, graph_score, graph_reasons (from graph_analysis.analyze_graph) - optional
    Returns: account_id, ml_score, rule_score, graph_score, final_score, risk_level, reasons
    """
    merged = pd.merge(ml_df, rule_df, on="account_id", how="outer")
    merged["rule_score"] = merged["rule_score"].fillna(0)
    merged["ml_score"] = merged["ml_score"].fillna(0)
    if graph_df is not None and not graph_df.empty:
        # only take needed cols
        g = graph_df[["account_id", "graph_score", "graph_reasons"]]
        merged = pd.merge(merged, g, on="account_id", how="left")
        merged["graph_score"] = merged["graph_score"].fillna(graph_score_default)
        merged["graph_reasons"] = merged["graph_reasons"].apply(lambda x: x if isinstance(x, list) else [])
    else:
        merged["graph_score"] = graph_score_default
        merged["graph_reasons"] = [[] for _ in range(len(merged))]

    out_rows = []
    for _, r in merged.iterrows():
        ml_s = float(r["ml_score"])
        rule_s = float(r["rule_score"])
        graph_s = float(r["graph_score"])
        final = round(WEIGHTS["ml"]*ml_s + WEIGHTS["rule"]*rule_s + WEIGHTS["graph"]*graph_s, 2)
        final = max(0, min(100, final))
        level = classify(final)
        # Build explainable reasons: ML + Rules + Graph
        reasons = []
        if ml_s >= 70:
            reasons.append(f"High anomaly score ({ml_s:.0f}/100) vs peer accounts - unusual behavior.")
        elif ml_s >= 50:
            reasons.append(f"Moderate anomaly score ({ml_s:.0f}/100) - deviates from normal patterns.")
        rule_reasons = r["reasons"] if isinstance(r["reasons"], list) else []
        if rule_reasons and rule_reasons[0] != "No behavioral rule triggered - activity appears normal.":
            reasons.extend(rule_reasons)
        elif ml_s < 30 and not (isinstance(r.get("graph_reasons"), list) and len(r.get("graph_reasons"))>0):
            reasons.append("Activity within normal range for peer group.")
        elif ml_s < 50:
            reasons.append("No strong behavioral flag, but anomaly score warrants review.")
        # Graph explanations (backed by actual calculations)
        graph_reasons = r.get("graph_reasons", [])
        if isinstance(graph_reasons, list) and graph_reasons:
            reasons.extend(graph_reasons)
        # cap and keep most informative (ML + top rules + graph)
        reasons = reasons[:8]

        out_rows.append({
            "account_id": r["account_id"],
            "ml_score": round(ml_s,2),
            "rule_score": round(rule_s,2),
            "graph_score": round(graph_s,2),
            "final_score": round(final,2),
            "risk_level": level,
            "reasons": reasons,
            "triggered_rules": r.get("triggered_rules", [])
        })
    return pd.DataFrame(out_rows)

if __name__ == "__main__":
    from features import extract_features_from_db
    from model import score_accounts
    from rules import evaluate_rules
    from graph_analysis import analyze_graph
    df = extract_features_from_db()
    ml = score_accounts(df)
    rules = evaluate_rules(df)
    graph_df, stats, _ = analyze_graph()
    risk = combine_scores(ml, rules, graph_df)
    print(risk.sort_values("final_score", ascending=False).head(10).to_string(index=False))
    print(risk["risk_level"].value_counts().to_string())
    print("Weights:", WEIGHTS)
