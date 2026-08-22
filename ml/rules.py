"""
Rule engine - explainable behavioral signals.
Each rule returns triggered, score contribution, and human-readable reason.
Thresholds are configurable and justified by synthetic data distribution.
"""
import pandas as pd

# Thresholds - tuned after inspecting normal vs mule distributions
THRESHOLDS = {
    "FAN_IN_COUNT": 15,        # unique_senders >15
    "FAN_OUT_COUNT": 12,       # unique_receivers >12 (mule fan-out uses 10-15)
    "VELOCITY": 1.0,          # velocity_per_hour >1.0 (normal ~0.04)
    "RAPID_DRAIN_RATIO": 0.85, # outflow close to inflow but rapid - proxied via ratio near 0.9 + high velocity
    "HIGH_TX_COUNT": 30,      # tx_count >30
    "MAX_AMOUNT_FACTOR": 2.5, # max_amount > 2.5 * avg_amount (spike)
    "COUNTERPARTY_EXPLOSION": 20, # unique_senders+receivers >20
}

def evaluate_rules(df):
    """
    Input: features DataFrame (one row per account)
    Output: DataFrame with rule_score 0-100 and list of triggered reasons
    """
    results = []
    for _, row in df.iterrows():
        triggered = []
        score = 0
        reasons = []

        # Rule 1: High fan-in
        if row["unique_senders"] > THRESHOLDS["FAN_IN_COUNT"]:
            triggered.append("HIGH_FAN_IN")
            score += 25
            reasons.append(f"Received funds from {int(row['unique_senders'])} unique accounts (threshold {THRESHOLDS['FAN_IN_COUNT']}) - possible fan-in.")

        # Rule 2: High fan-out
        if row["unique_receivers"] > THRESHOLDS["FAN_OUT_COUNT"]:
            triggered.append("HIGH_FAN_OUT")
            score += 25
            reasons.append(f"Sent funds to {int(row['unique_receivers'])} unique accounts (threshold {THRESHOLDS['FAN_OUT_COUNT']}) - possible fan-out.")

        # Rule 3: High velocity
        if row["velocity_per_hour"] > THRESHOLDS["VELOCITY"]:
            triggered.append("HIGH_VELOCITY")
            score += 20
            reasons.append(f"Unusually high transaction velocity: {row['velocity_per_hour']:.2f}/hour (threshold {THRESHOLDS['VELOCITY']}).")

        # Rule 4: Rapid drain proxy - high outflow ratio + high velocity + high total_in
        if row["total_in"] > 8000 and row["velocity_per_hour"] > 0.5 and 0.85 <= row["inflow_outflow_ratio"] <= 1.05:
            # for mule rapid drain, inflow~outflow and fast
            # also check if total_in large and tx completed fast (<10 min implied by high velocity)
            if row["velocity_per_hour"] > 5 or row["fan_out_score"] >= 1:
                triggered.append("RAPID_DRAIN")
                score += 30
                pct = min(row["total_out"]/row["total_in"]*100 if row["total_in"]>0 else 0, 100)
                reasons.append(f"Moved {pct:.0f}% of incoming funds quickly (rapid drain pattern).")

        # Rule 5: Counterparty explosion
        total_cp = int(row["unique_senders"] + row["unique_receivers"])
        if total_cp > THRESHOLDS["COUNTERPARTY_EXPLOSION"]:
            triggered.append("COUNTERPARTY_EXPLOSION")
            score += 15
            reasons.append(f"Unusually large counterparty network: {total_cp} unique counterparties.")

        # Rule 6: High tx count
        if row["tx_count"] > THRESHOLDS["HIGH_TX_COUNT"]:
            triggered.append("HIGH_TX_COUNT")
            score += 15
            reasons.append(f"High transaction count: {int(row['tx_count'])} transactions (threshold {THRESHOLDS['HIGH_TX_COUNT']}).")

        # Rule 7: Amount spike
        if row["avg_amount"] > 0 and row["max_amount"] > THRESHOLDS["MAX_AMOUNT_FACTOR"] * row["avg_amount"] and row["max_amount"] > 5000:
            triggered.append("AMOUNT_SPIKE")
            score += 10
            reasons.append(f"Large transaction deviation: max {row['max_amount']:.0f} vs avg {row['avg_amount']:.0f}.")

        # Cap at 100
        rule_score = min(score, 100)
        if not reasons:
            reasons = ["No behavioral rule triggered - activity appears normal."]

        results.append({
            "account_id": row["account_id"],
            "rule_score": rule_score,
            "triggered_rules": triggered,
            "reasons": reasons
        })
    return pd.DataFrame(results)

if __name__ == "__main__":
    from features import extract_features_from_db
    df = extract_features_from_db()
    out = evaluate_rules(df)
    print(out.sort_values("rule_score", ascending=False).head(10).to_string(index=False))
    print(f"Triggered accounts: {(out.rule_score>0).sum()} / {len(out)}")
