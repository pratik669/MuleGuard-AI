"""
MuleGuard Risk Engine - Phase 3

Combines:
    ML anomaly score
    Behavioral rule score
    Graph intelligence score
    Money-flow intelligence score

Final score:
    ML       = 35%
    Rules    = 25%
    Graph    = 20%
    Flow     = 20%

These are initial experimental weights for the hackathon MVP.
They are not statistically validated.
"""

import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

WEIGHTS = {
    "ml": 0.35,
    "rule": 0.25,
    "graph": 0.20,
    "flow": 0.20,
}

LEVELS = [
    (80, "CRITICAL"),
    (60, "HIGH"),
    (30, "MEDIUM"),
    (0, "LOW"),
]


# ============================================================
# RISK CLASSIFICATION
# ============================================================

def classify(score):
    for threshold, level in LEVELS:
        if score >= threshold:
            return level

    return "LOW"


# ============================================================
# COMBINE EVIDENCE
# ============================================================

def combine_scores(
    ml_df,
    rule_df,
    graph_df=None,
    flow_df=None,
    graph_score_default=0,
    flow_score_default=0,
):

    """
    Combine ML + Rules + Graph + Flow.

    Required columns:

    ml_df:
        account_id
        ml_score

    rule_df:
        account_id
        rule_score
        triggered_rules
        reasons

    graph_df:
        account_id
        graph_score
        graph_reasons

    flow_df:
        account_id
        flow_score
        flow_reasons
    """

    # --------------------------------------------------------
    # ML + Rules
    # --------------------------------------------------------

    merged = pd.merge(
        ml_df,
        rule_df,
        on="account_id",
        how="outer",
    )

    merged["ml_score"] = merged["ml_score"].fillna(0)
    merged["rule_score"] = merged["rule_score"].fillna(0)

    # --------------------------------------------------------
    # Graph
    # --------------------------------------------------------

    if graph_df is not None and not graph_df.empty:

        graph_columns = [
            "account_id",
            "graph_score",
            "graph_reasons",
        ]

        available = [
            col
            for col in graph_columns
            if col in graph_df.columns
        ]

        g = graph_df[available].copy()

        merged = pd.merge(
            merged,
            g,
            on="account_id",
            how="left",
        )

        if "graph_score" not in merged.columns:
            merged["graph_score"] = graph_score_default

        if "graph_reasons" not in merged.columns:
            merged["graph_reasons"] = [[] for _ in range(len(merged))]

    else:

        merged["graph_score"] = graph_score_default
        merged["graph_reasons"] = [[] for _ in range(len(merged))]

    merged["graph_score"] = merged["graph_score"].fillna(
        graph_score_default
    )

    merged["graph_reasons"] = merged["graph_reasons"].apply(
        lambda x: x if isinstance(x, list) else []
    )

    # --------------------------------------------------------
    # Flow
    # --------------------------------------------------------

    if flow_df is not None and not flow_df.empty:

        flow_columns = [
            "account_id",
            "flow_score",
            "flow_reasons",
        ]

        available = [
            col
            for col in flow_columns
            if col in flow_df.columns
        ]

        f = flow_df[available].copy()

        merged = pd.merge(
            merged,
            f,
            on="account_id",
            how="left",
        )

        if "flow_score" not in merged.columns:
            merged["flow_score"] = flow_score_default

        if "flow_reasons" not in merged.columns:
            merged["flow_reasons"] = [[] for _ in range(len(merged))]

    else:

        merged["flow_score"] = flow_score_default
        merged["flow_reasons"] = [[] for _ in range(len(merged))]

    merged["flow_score"] = merged["flow_score"].fillna(
        flow_score_default
    )

    merged["flow_reasons"] = merged["flow_reasons"].apply(
        lambda x: x if isinstance(x, list) else []
    )

    # ========================================================
    # FINAL RISK CALCULATION
    # ========================================================

    output = []

    for _, row in merged.iterrows():

        account_id = row["account_id"]

        ml_score = float(row["ml_score"])
        rule_score = float(row["rule_score"])
        graph_score = float(row["graph_score"])
        flow_score = float(row["flow_score"])

        # ----------------------------------------------------
        # Weighted final score
        # ----------------------------------------------------

        final_score = (
            WEIGHTS["ml"] * ml_score
            + WEIGHTS["rule"] * rule_score
            + WEIGHTS["graph"] * graph_score
            + WEIGHTS["flow"] * flow_score
        )

        final_score = max(
            0,
            min(
                100,
                round(final_score, 2),
            ),
        )

        risk_level = classify(final_score)

        # ====================================================
        # EXPLAINABLE REASONS
        # ====================================================

        reasons = []

        # ----------------------------------------------------
        # ML explanation
        # ----------------------------------------------------

        if ml_score >= 70:

            reasons.append(
                f"High anomaly score ({ml_score:.0f}/100) "
                f"indicating unusual account behavior."
            )

        elif ml_score >= 50:

            reasons.append(
                f"Moderate anomaly score ({ml_score:.0f}/100) "
                f"showing deviation from peer behavior."
            )

        # ----------------------------------------------------
        # Rule explanations
        # ----------------------------------------------------

        rule_reasons = row.get("reasons", [])

        if isinstance(rule_reasons, list):

            for reason in rule_reasons:

                if (
                    reason
                    and reason
                    != "No behavioral rule triggered - activity appears normal."
                ):

                    reasons.append(str(reason))

        # ----------------------------------------------------
        # Graph explanations
        # ----------------------------------------------------

        graph_reasons = row.get(
            "graph_reasons",
            [],
        )

        if isinstance(graph_reasons, list):

            for reason in graph_reasons:

                if reason:
                    reasons.append(str(reason))

        # ----------------------------------------------------
        # Flow explanations
        # ----------------------------------------------------

        flow_reasons = row.get(
            "flow_reasons",
            [],
        )

        if isinstance(flow_reasons, list):

            for reason in flow_reasons:

                if reason:
                    reasons.append(str(reason))

        # ----------------------------------------------------
        # Fallback explanation
        # ----------------------------------------------------

        if not reasons:

            reasons.append(
                "No strong risk indicators detected."
            )

        # Keep explanations manageable
        reasons = reasons[:8]

        # ====================================================
        # OUTPUT ROW
        # ====================================================

        output.append(
            {
                "account_id": account_id,

                "ml_score": round(
                    ml_score,
                    2,
                ),

                "rule_score": round(
                    rule_score,
                    2,
                ),

                "graph_score": round(
                    graph_score,
                    2,
                ),

                "flow_score": round(
                    flow_score,
                    2,
                ),

                "final_score": final_score,

                "risk_level": risk_level,

                "reasons": reasons,

                "triggered_rules": (
                    row.get(
                        "triggered_rules",
                        [],
                    )
                ),
            }
        )

    return pd.DataFrame(output)


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    from features import extract_features_from_db
    from model import score_accounts
    from rules import evaluate_rules
    from graph_analysis import analyze_graph
    from flow_intelligence import analyze_flow

    print("=" * 60)
    print("MuleGuard Risk Engine Test")
    print("=" * 60)

    df = extract_features_from_db()

    ml = score_accounts(df)

    rules = evaluate_rules(df)

    graph_df, stats, _ = analyze_graph()

    flow_df = analyze_flow()

    risk = combine_scores(
        ml_df=ml,
        rule_df=rules,
        graph_df=graph_df,
        flow_df=flow_df,
    )

    print("\nTop 10 highest-risk accounts:")

    print(
        risk
        .sort_values(
            "final_score",
            ascending=False,
        )
        .head(10)
        .to_string(index=False)
    )

    print("\nRisk distribution:")

    print(
        risk["risk_level"]
        .value_counts()
        .to_string()
    )

    print("\nWeights:")

    print(WEIGHTS)