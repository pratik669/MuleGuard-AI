"""
MuleGuard Single-Command Pipeline

Pipeline:

Features
   ↓
Isolation Forest
   ↓
Behavioral Rules
   ↓
Graph Intelligence
   ↓
Flow Intelligence
   ↓
Evidence Fusion
   ↓
PostgreSQL
"""

import os
import json

import psycopg

from dotenv import load_dotenv

from features import (
    extract_features_from_db,
    save_features
)

from model import (
    score_accounts
)

from rules import (
    evaluate_rules
)

from graph_analysis import (
    analyze_graph
)

from flow_intelligence import (
    analyze_flow
)

from risk import (
    combine_scores,
    WEIGHTS
)


load_dotenv()

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/muleguard"
)


def run():

    print("=" * 60)
    print("MuleGuard pipeline")
    print("=" * 60)

    # ========================================================
    # 1. FEATURES
    # ========================================================

    print(
        "\n[1/6] Extracting features..."
    )

    df = extract_features_from_db()

    print(
        f"  Accounts analyzed: "
        f"{len(df)}"
    )

    save_features(
        df,
        to_db=True
    )

    # ========================================================
    # 2. ML
    # ========================================================

    print(
        "\n[2/6] Running Isolation Forest..."
    )

    ml_scores = score_accounts(df)

    print(
        f"  ML mean: "
        f"{ml_scores.ml_score.mean():.1f}"
    )

    print(
        "  Top anomalous accounts:"
    )

    for _, row in (
        ml_scores
        .sort_values(
            "ml_score",
            ascending=False
        )
        .head(5)
        .iterrows()
    ):

        print(
            f"    {row.account_id}: "
            f"{row.ml_score:.1f}"
        )

    # ========================================================
    # 3. RULES
    # ========================================================

    print(
        "\n[3/6] Evaluating behavioral rules..."
    )

    rule_out = evaluate_rules(df)

    print(
        f"  Accounts with rule flags: "
        f"{(rule_out.rule_score > 0).sum()}"
    )

    # ========================================================
    # 4. GRAPH
    # ========================================================

    print(
        "\n[4/6] Building transaction graph..."
    )

    graph_df, stats, _ = (
        analyze_graph()
    )

    print(
        f"  Graph: "
        f"{stats['nodes']} nodes, "
        f"{stats['edges_multi']} transaction edges"
    )

    print(
        f"  Chains: "
        f"{len(stats['chains'])}"
    )

    print(
        f"  Cycles: "
        f"{len(stats['cycles'])}"
    )

    print(
        f"  Graph score mean: "
        f"{graph_df.graph_score.mean():.1f}"
    )

    # ========================================================
    # 5. FLOW
    # ========================================================

    print(
        "\n[5/6] Analyzing money-flow behavior..."
    )

    flow_df = analyze_flow()

    print(
        f"  Flow score mean: "
        f"{flow_df.flow_score.mean():.1f}"
    )

    print(
        "  Top flow-risk accounts:"
    )

    for _, row in (
        flow_df
        .sort_values(
            "flow_score",
            ascending=False
        )
        .head(5)
        .iterrows()
    ):

        print(
            f"    {row.account_id}: "
            f"{row.flow_score:.1f}"
        )

    # ========================================================
    # 6. FINAL RISK
    # ========================================================

    print(
        "\n[6/6] Combining evidence..."
    )

    print(
        "  Weights:"
    )

    print(
        f"    ML    = {WEIGHTS['ml'] * 100:.0f}%"
    )

    print(
        f"    Rules = {WEIGHTS['rule'] * 100:.0f}%"
    )

    print(
        f"    Graph = {WEIGHTS['graph'] * 100:.0f}%"
    )

    print(
        f"    Flow  = {WEIGHTS['flow'] * 100:.0f}%"
    )

    risk_df = combine_scores(
        ml_scores,
        rule_out,
        graph_df,
        flow_df
    )

    # ========================================================
    # PERSIST
    # ========================================================

    with psycopg.connect(DB_URL) as conn:

        with conn.cursor() as cur:

            # Add flow_score column if necessary.
            cur.execute(
                """
                ALTER TABLE risk_scores
                ADD COLUMN IF NOT EXISTS
                flow_score REAL
                """
            )

            cur.execute(
                "DELETE FROM risk_scores"
            )

            for _, row in (
                risk_df.iterrows()
            ):

                cur.execute(
                    """
                    INSERT INTO risk_scores
                    (
                        account_id,
                        ml_score,
                        rule_score,
                        graph_score,
                        flow_score,
                        final_score,
                        risk_level,
                        reasons
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s::jsonb
                    )
                    """,
                    (
                        row.account_id,
                        float(row.ml_score),
                        float(row.rule_score),
                        float(row.graph_score),
                        float(row.flow_score),
                        float(row.final_score),
                        row.risk_level,
                        json.dumps(
                            row.reasons
                        )
                    )
                )

        conn.commit()

    # ========================================================
    # SUMMARY
    # ========================================================

    print(
        "\n" + "=" * 60
    )

    print(
        "FINAL MULEGUARD RESULTS"
    )

    print(
        "=" * 60
    )

    with psycopg.connect(DB_URL) as conn:

        with conn.cursor() as cur:

            cur.execute(
                "SELECT COUNT(*) FROM accounts"
            )

            accounts = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM transactions"
            )

            transactions = (
                cur.fetchone()[0]
            )

            cur.execute(
                """
                SELECT id
                FROM accounts
                WHERE id LIKE 'M%%'
                """
            )

            mule_ids = {
                row[0]
                for row in cur.fetchall()
            }

    print(
        f"Accounts: {accounts}"
    )

    print(
        f"Transactions: {transactions}"
    )

    print(
        "\nHighest-risk accounts:"
    )

    for _, row in (
        risk_df
        .sort_values(
            "final_score",
            ascending=False
        )
        .head(15)
        .iterrows()
    ):

        marker = (
            " <-- MULE"
            if row.account_id in mule_ids
            else ""
        )

        print(
            f"{row.account_id:6} | "
            f"final={row.final_score:5.1f} | "
            f"{row.risk_level:8} | "
            f"ML={row.ml_score:5.1f} | "
            f"Rules={row.rule_score:5.1f} | "
            f"Graph={row.graph_score:5.1f} | "
            f"Flow={row.flow_score:5.1f}"
            f"{marker}"
        )

    print(
        "\nRisk distribution:"
    )

    print(
        risk_df[
            "risk_level"
        ]
        .value_counts()
        .to_string()
    )

    # ========================================================
    # EVALUATION
    # ========================================================

    top_k = 25

    top_ids = set(
        risk_df
        .sort_values(
            "final_score",
            ascending=False
        )
        .head(top_k)
        ["account_id"]
    )

    true_positives = (
        top_ids & mule_ids
    )

    tp = len(true_positives)

    precision = tp / top_k

    recall = (
        tp / len(mule_ids)
        if mule_ids
        else 0
    )

    if precision + recall > 0:

        f1 = (
            2 * precision * recall
            / (precision + recall)
        )

    else:

        f1 = 0

    print(
        "\n===== SYNTHETIC EVALUATION ====="
    )

    print(
        f"Top-{top_k} mule detection: "
        f"{tp}/{top_k}"
    )

    print(
        f"Precision@{top_k}: "
        f"{precision * 100:.2f}%"
    )

    print(
        f"Recall@{top_k}: "
        f"{recall * 100:.2f}%"
    )

    print(
        f"F1@{top_k}: "
        f"{f1 * 100:.2f}%"
    )

    print(
        "\nMules in top-25:"
    )

    print(
        sorted(true_positives)
    )

    print(
        "\nPipeline complete."
    )


if __name__ == "__main__":
    run()