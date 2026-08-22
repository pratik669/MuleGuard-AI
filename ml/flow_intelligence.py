"""
MuleGuard - Flow Intelligence

Detects suspicious money-flow behavior from transaction timing,
amount preservation, and distribution patterns.

This is an evidence layer, not a standalone fraud classifier.
"""

import os
import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/muleguard"
)

MIN_AMOUNT = 5000

RAPID_MINUTES = 30
VERY_RAPID_MINUTES = 15

PASS_LOW = 0.85
PASS_HIGH = 1.15


def load_transactions():
    query = """
        SELECT
            id,
            from_account,
            to_account,
            amount,
            timestamp
        FROM transactions
        ORDER BY timestamp
    """

    with psycopg.connect(DB_URL) as conn:
        tx = pd.read_sql(query, conn)

    tx["timestamp"] = pd.to_datetime(tx["timestamp"])

    return tx


def analyze_account(account_id, tx):
    incoming = tx[
        tx["to_account"] == account_id
    ].sort_values("timestamp")

    outgoing = tx[
        tx["from_account"] == account_id
    ].sort_values("timestamp")

    score = 0
    reasons = []
    evidence = []

    total_in = float(incoming["amount"].sum())
    total_out = float(outgoing["amount"].sum())

    in_count = len(incoming)
    out_count = len(outgoing)

    # ========================================================
    # 1. RAPID PASS-THROUGH
    # ========================================================

    if in_count > 0 and out_count > 0:

        for _, inc in incoming.iterrows():

            inc_amount = float(inc["amount"])
            inc_time = inc["timestamp"]

            if inc_amount < MIN_AMOUNT:
                continue

            later = outgoing[
                outgoing["timestamp"] >= inc_time
            ].copy()

            if later.empty:
                continue

            later["delay_min"] = (
                later["timestamp"] - inc_time
            ).dt.total_seconds() / 60

            rapid = later[
                later["delay_min"] <= RAPID_MINUTES
            ]

            if rapid.empty:
                continue

            rapid_out = float(
                rapid["amount"].sum()
            )

            ratio = rapid_out / inc_amount

            if (
                rapid_out >= MIN_AMOUNT
                and PASS_LOW <= ratio <= PASS_HIGH
            ):

                fastest = float(
                    rapid["delay_min"].min()
                )

                if fastest <= VERY_RAPID_MINUTES:
                    contribution = 35
                    label = "RAPID_PASS_THROUGH"

                else:
                    contribution = 25
                    label = "PASS_THROUGH"

                score += contribution

                evidence.append(label)

                reasons.append(
                    f"{label}: received "
                    f"{inc_amount:.0f} and moved "
                    f"{rapid_out:.0f} within "
                    f"{fastest:.1f} minutes "
                    f"(ratio={ratio:.2f})."
                )

                break

    # ========================================================
    # 2. DISTRIBUTED FAN-OUT
    # ========================================================

    # This specifically targets the M0006-M0010 pattern.
    #
    # One meaningful incoming transaction
    # followed by many outgoing transactions
    # with most value distributed.

    if (
        in_count == 1
        and out_count >= 8
    ):

        inc = incoming.iloc[0]

        inc_amount = float(
            inc["amount"]
        )

        inc_time = inc["timestamp"]

        if inc_amount >= MIN_AMOUNT:

            later = outgoing[
                outgoing["timestamp"] >= inc_time
            ].copy()

            if not later.empty:

                later["delay_min"] = (
                    later["timestamp"] - inc_time
                ).dt.total_seconds() / 60

                within_window = later[
                    later["delay_min"] <= 60
                ]

                distributed_out = float(
                    within_window["amount"].sum()
                )

                ratio = (
                    distributed_out / inc_amount
                )

                receivers = (
                    within_window["to_account"]
                    .nunique()
                )

                if (
                    receivers >= 8
                    and PASS_LOW <= ratio <= 1.10
                ):

                    score += 35

                    evidence.append(
                        "DISTRIBUTED_FAN_OUT"
                    )

                    reasons.append(
                        f"Distributed fan-out: one incoming "
                        f"payment of {inc_amount:.0f} followed "
                        f"by {receivers} outgoing recipients "
                        f"within 60 minutes, retaining "
                        f"{ratio:.2f} of value."
                    )

    # ========================================================
    # 3. MULTI-OUT VALUE DISTRIBUTION
    # ========================================================

    if (
        out_count >= 5
        and total_in >= MIN_AMOUNT
        and total_out >= MIN_AMOUNT
    ):

        overall_ratio = total_out / total_in

        if (
            PASS_LOW <= overall_ratio <= 1.10
            and not any(
                "DISTRIBUTED_FAN_OUT" in x
                for x in evidence
            )
        ):

            score += 15

            evidence.append(
                "VALUE_DISTRIBUTION"
            )

            reasons.append(
                f"Multiple outgoing transfers "
                f"distributed {total_out:.0f} from "
                f"{total_in:.0f} incoming value "
                f"(ratio={overall_ratio:.2f})."
            )

    # ========================================================
    # 4. DESTINATION PATTERN
    # ========================================================

    # Many incoming transfers with no outgoing movement
    # is useful evidence, but deliberately weak.

    if (
        in_count >= 12
        and out_count == 0
        and total_in >= MIN_AMOUNT
    ):

        score += 10

        evidence.append(
            "HIGH_FAN_IN_DESTINATION"
        )

        reasons.append(
            f"Received {in_count} incoming "
            f"transactions totaling "
            f"{total_in:.0f} without outgoing "
            f"movement."
        )

    # ========================================================
    # FINAL SCORE
    # ========================================================

    score = min(score, 100)

    if not reasons:
        reasons.append(
            "No strong suspicious money-flow pattern detected."
        )

    return {
        "account_id": account_id,
        "flow_score": round(score, 2),
        "flow_reasons": reasons,
        "flow_evidence": evidence
    }


def analyze_flow():

    tx = load_transactions()

    accounts = sorted(
        set(tx["from_account"].unique())
        | set(tx["to_account"].unique())
    )

    rows = []

    for account_id in accounts:

        rows.append(
            analyze_account(
                account_id,
                tx
            )
        )

    return pd.DataFrame(rows)


if __name__ == "__main__":

    df = analyze_flow()

    print("=" * 60)
    print("MuleGuard - FLOW INTELLIGENCE")
    print("=" * 60)

    print(
        f"Accounts analyzed: {len(df)}"
    )

    print("\nTop flow-risk accounts:")

    print(
        df.sort_values(
            "flow_score",
            ascending=False
        )
        .head(25)
        .to_string(index=False)
    )