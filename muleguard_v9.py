"""
MuleGuard - FINAL FUSION V9

Combines:
1. Existing ML + Rules + Graph risk score from risk_scores
2. Chain-risk signals
3. Account-behavior signals
4. Circular-return detection
5. Multi-hop source behavior

Experimental fusion layer.
Does NOT modify the existing MuleGuard pipeline.
"""

import os
import pandas as pd
import psycopg
from dotenv import load_dotenv

from ml.graph_analysis import analyze_graph


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/muleguard"
)

MIN_AMOUNT = 5000

RAPID_TIME = 30
VERY_RAPID_TIME = 15

PASS_RATIO_LOW = 0.80
PASS_RATIO_HIGH = 1.20


# Chain signal weights
RAPID_PASS_SCORE = 40
INTERMEDIARY_SCORE = 25
MULTI_HOP_SCORE = 30
DESTINATION_SCORE = 5
PARTIAL_DRAIN_SCORE = 35
CIRCULAR_SCORE = 40


# ============================================================
# BASIC HELPERS
# ============================================================

def value_preserving(incoming, outgoing):
    if incoming <= 0:
        return False

    ratio = outgoing / incoming

    return (
        PASS_RATIO_LOW
        <= ratio
        <= PASS_RATIO_HIGH
    )


# ============================================================
# LOAD EXISTING REAL RISK SCORES
# ============================================================

def load_base_scores():

    sql = """
        SELECT
            account_id,
            final_score,
            ml_score,
            rule_score,
            graph_score
        FROM risk_scores
    """

    with psycopg.connect(DB_URL) as conn:
        rows = conn.execute(sql).fetchall()

    data = {}

    for row in rows:

        account_id = row[0]

        data[account_id] = {
            "final": float(row[1] or 0),
            "ml": float(row[2] or 0),
            "rule": float(row[3] or 0),
            "graph": float(row[4] or 0),
        }

    return data


# ============================================================
# CHAIN SCORING
# ============================================================

def calculate_chain_signal(account_id, chains):

    score = 0
    signals = []

    for chain in chains:

        nodes = chain.get("nodes", [])
        amounts = chain.get("amounts", [])
        span = float(chain.get("span_min", 999999))

        if account_id not in nodes:
            continue

        position = nodes.index(account_id)

        # ----------------------------------------------------
        # SOURCE
        # ----------------------------------------------------

        if position == 0:

            if len(nodes) >= 4 and amounts:

                amount = float(amounts[0])

                if amount >= MIN_AMOUNT and span <= 180:

                    score += MULTI_HOP_SCORE

                    signals.append(
                        f"MULTI_HOP_SOURCE "
                        f"(amount={amount:.0f}, "
                        f"nodes={len(nodes)}, "
                        f"span={span:.1f}m)"
                    )

        # ----------------------------------------------------
        # INTERMEDIARY
        # ----------------------------------------------------

        elif position < len(nodes) - 1:

            if len(amounts) <= position:
                continue

            incoming = float(amounts[position - 1])
            outgoing = float(amounts[position])

            if incoming < MIN_AMOUNT:
                continue

            if (
                outgoing >= MIN_AMOUNT
                and value_preserving(incoming, outgoing)
                and span <= VERY_RAPID_TIME
            ):

                score += RAPID_PASS_SCORE

                ratio = outgoing / incoming

                signals.append(
                    f"RAPID_PASS_THROUGH "
                    f"(in={incoming:.0f}, "
                    f"out={outgoing:.0f}, "
                    f"ratio={ratio:.2f}, "
                    f"span={span:.1f}m)"
                )

            elif (
                outgoing >= MIN_AMOUNT
                and value_preserving(incoming, outgoing)
                and span <= RAPID_TIME
            ):

                score += INTERMEDIARY_SCORE

                ratio = outgoing / incoming

                signals.append(
                    f"INTERMEDIARY_PASS "
                    f"(ratio={ratio:.2f}, "
                    f"span={span:.1f}m)"
                )

            # ------------------------------------------------
            # PARTIAL DRAIN
            # ------------------------------------------------

            elif (
                incoming >= MIN_AMOUNT
                and outgoing >= 0
                and outgoing / incoming < 0.50
                and span <= 30
            ):

                score += PARTIAL_DRAIN_SCORE

                ratio = outgoing / incoming

                signals.append(
                    f"PARTIAL_DRAIN "
                    f"(in={incoming:.0f}, "
                    f"out={outgoing:.0f}, "
                    f"ratio={ratio:.2f}, "
                    f"span={span:.1f}m)"
                )

        # ----------------------------------------------------
        # DESTINATION
        # ----------------------------------------------------

        else:

            if amounts:

                incoming = float(amounts[-1])

                if incoming >= MIN_AMOUNT:

                    score += DESTINATION_SCORE

                    signals.append(
                        f"DESTINATION "
                        f"(amount={incoming:.0f}, "
                        f"span={span:.1f}m)"
                    )

    return min(score, 100), signals


# ============================================================
# CIRCULAR RETURNS
# ============================================================

def detect_circular_returns():

    sql = """
        SELECT
            from_account,
            to_account,
            amount,
            timestamp
        FROM transactions
        ORDER BY timestamp
    """

    try:

        with psycopg.connect(DB_URL) as conn:
            rows = conn.execute(sql).fetchall()

    except Exception as e:

        print(f"Circular detection warning: {e}")
        return {}

    transactions = {}

    for row in rows:

        src = row[0]
        dst = row[1]
        amount = float(row[2])
        timestamp = row[3]

        transactions.setdefault(src, []).append(
            (dst, amount, timestamp)
        )

    circular = {}

    # Look for A -> B -> C -> A
    for src, outgoing in transactions.items():

        for b, amount1, time1 in outgoing:

            for c, amount2, time2 in transactions.get(b, []):

                if c == src:
                    continue

                for dst, amount3, time3 in transactions.get(c, []):

                    if dst != src:
                        continue

                    span = (
                        time3 - time1
                    ).total_seconds() / 60

                    if span < 0 or span > 180:
                        continue

                    retention = (
                        amount3 / amount1
                        if amount1 > 0
                        else 0
                    )

                    if (
                        amount1 >= MIN_AMOUNT
                        and 0.80 <= retention <= 1.20
                    ):

                        circular[src] = {
                            "amount": amount1,
                            "retention": retention,
                            "span": span
                        }

    return circular


# ============================================================
# ACCOUNT BEHAVIOR
# ============================================================

def load_behavior():

    sql = """
        SELECT
            from_account,
            to_account,
            amount,
            timestamp
        FROM transactions
    """

    with psycopg.connect(DB_URL) as conn:
        rows = conn.execute(sql).fetchall()

    behavior = {}

    for src, dst, amount, timestamp in rows:

        amount = float(amount)

        if src not in behavior:
            behavior[src] = {
                "out": 0,
                "out_count": 0,
                "receivers": set(),
                "times": []
            }

        if dst not in behavior:
            behavior[dst] = {
                "out": 0,
                "out_count": 0,
                "receivers": set(),
                "times": []
            }

        behavior[src]["out"] += amount
        behavior[src]["out_count"] += 1
        behavior[src]["receivers"].add(dst)
        behavior[src]["times"].append(timestamp)

        behavior[dst]["times"].append(timestamp)

    return behavior


def behavior_signal(account_id, behavior):

    if account_id not in behavior:
        return 0, []

    b = behavior[account_id]

    score = 0
    signals = []

    out_count = b["out_count"]
    receiver_count = len(b["receivers"])
    total_out = b["out"]

    # FAN OUT
    if receiver_count >= 10 and total_out >= MIN_AMOUNT:

        score += 10

        signals.append(
            f"FAN_OUT "
            f"(receivers={receiver_count}, "
            f"out={total_out:.0f})"
        )

    elif receiver_count >= 5:

        score += 5

        signals.append(
            f"FAN_OUT "
            f"(receivers={receiver_count})"
        )

    # HIGH VELOCITY
    times = b["times"]

    if len(times) >= 4:

        span = (
            max(times) - min(times)
        ).total_seconds() / 60

        if 0 < span <= 15:

            score += 10

            signals.append(
                f"HIGH_VELOCITY "
                f"(tx={len(times)}, "
                f"span={span:.1f}m)"
            )

    return score, signals


# ============================================================
# FUSION
# ============================================================

def calculate_final_score(
    base_score,
    chain_score,
    behavior_score,
    circular
):

    # Existing risk score remains the dominant signal.
    score = base_score

    # Chain evidence
    score += chain_score * 0.25

    # Behavior evidence
    score += behavior_score * 0.30

    # Strong circular evidence
    if circular:
        score += 12

    return min(score, 100)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("MuleGuard - FINAL FUSION V9")
    print("=" * 70)

    # --------------------------------------------------------
    # Existing graph analysis
    # --------------------------------------------------------

    df, stats, _ = analyze_graph()

    chains = stats["chains"]

    print(f"\nAccounts : {len(df)}")
    print(f"Chains   : {len(chains)}")

    # --------------------------------------------------------
    # Existing real risk scores
    # --------------------------------------------------------

    base_scores = load_base_scores()

    print(
        f"Risk-score records loaded : "
        f"{len(base_scores)}"
    )

    # --------------------------------------------------------
    # Circular returns
    # --------------------------------------------------------

    print("\nDetecting circular returns...")

    circular = detect_circular_returns()

    print(
        f"Circular returns detected: "
        f"{len(circular)}"
    )

    # --------------------------------------------------------
    # Behavior
    # --------------------------------------------------------

    behavior = load_behavior()

    # --------------------------------------------------------
    # Calculate
    # --------------------------------------------------------

    results = []

    for account_id in df["account_id"]:

        base = base_scores.get(
            account_id,
            {
                "final": 0,
                "ml": 0,
                "rule": 0,
                "graph": 0
            }
        )

        account_chains = [
            c
            for c in chains
            if account_id in c.get("nodes", [])
        ]

        chain_score, chain_signals = (
            calculate_chain_signal(
                account_id,
                account_chains
            )
        )

        behavior_score, behavior_signals = (
            behavior_signal(
                account_id,
                behavior
            )
        )

        circular_info = circular.get(account_id)

        circular_signal = []

        if circular_info:

            circular_signal.append(
                f"CIRCULAR_RETURN "
                f"(amount={circular_info['amount']:.0f}, "
                f"retention={circular_info['retention']:.2f}, "
                f"span={circular_info['span']:.1f}m)"
            )

        final = calculate_final_score(
            base["final"],
            chain_score,
            behavior_score,
            circular_info
        )

        signals = (
            chain_signals
            + behavior_signals
            + circular_signal
        )

        results.append({

            "account_id": account_id,

            "base": base["final"],
            "ml": base["ml"],
            "rule": base["rule"],
            "graph": base["graph"],

            "chain": chain_score,
            "behavior": behavior_score,

            "circular": (
                1 if circular_info else 0
            ),

            "final": final,

            "signals": signals
        })

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    results.sort(
        key=lambda x: x["final"],
        reverse=True
    )

    # --------------------------------------------------------
    # TOP 25
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("===== TOP 25 FINAL FUSION V9 =====")
    print("=" * 70)

    for i, row in enumerate(
        results[:25],
        start=1
    ):

        mule = (
            " <-- MULE"
            if row["account_id"].startswith("M")
            else ""
        )

        print(
            f"{i:2}. "
            f"{row['account_id']} | "
            f"base={row['base']:5.1f} | "
            f"chain={row['chain']:3} | "
            f"behavior={row['behavior']:2} | "
            f"new={row['final']:5.1f}"
            f"{mule}"
        )

        for signal in row["signals"]:

            print(
                f"    {signal}"
            )

    # --------------------------------------------------------
    # Known mules
    # --------------------------------------------------------

    mule_ids = {
        f"M{i:04d}"
        for i in range(1, 26)
    }

    top25 = {
        row["account_id"]
        for row in results[:25]
    }

    found = sorted(
        top25.intersection(mule_ids)
    )

    missed = sorted(
        mule_ids - top25
    )

    tp = len(found)

    precision = tp / 25
    recall = tp / 25

    if precision + recall > 0:

        f1 = (
            2 * precision * recall
            / (precision + recall)
        )

    else:

        f1 = 0

    # --------------------------------------------------------
    # Evaluation
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("===== V9 EVALUATION =====")
    print("=" * 70)

    print(
        f"Actual mule accounts : "
        f"{len(mule_ids)}"
    )

    print(
        f"Mules in top-25      : "
        f"{tp}/25"
    )

    print(
        f"Precision@25         : "
        f"{precision * 100:.2f}%"
    )

    print(
        f"Recall@25            : "
        f"{recall * 100:.2f}%"
    )

    print(
        f"F1@25                : "
        f"{f1 * 100:.2f}%"
    )

    print("\nMules found:")

    print(found)

    print("\nMules missed:")

    print(missed)

    # --------------------------------------------------------
    # All mule scores
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("===== ALL KNOWN MULES =====")
    print("=" * 70)

    for row in sorted(
        results,
        key=lambda x: x["account_id"]
    ):

        if row["account_id"] in mule_ids:

            print(
                f"{row['account_id']} | "
                f"base={row['base']:.1f} | "
                f"ML={row['ml']:.1f} | "
                f"Rule={row['rule']:.1f} | "
                f"Graph={row['graph']:.1f} | "
                f"Chain={row['chain']} | "
                f"Behavior={row['behavior']} | "
                f"Final={row['final']:.1f}"
            )

    print("\n" + "=" * 70)
    print("V9 COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()