"""
Isolation Forest - unsupervised anomaly detection.
Higher ml_score = more anomalous vs peers. NOT fraud probability.
"""
import os
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

RANDOM_STATE = 42
CONTAMINATION = 0.08  # expected anomaly proportion - configurable
FEATURE_COLS = [
    "total_in","total_out","cnt_in","cnt_out","unique_senders","unique_receivers",
    "avg_amount","max_amount","tx_count","inflow_outflow_ratio","fan_in_score",
    "fan_out_score","activity_duration_hours","velocity_per_hour"
]

def train_isolation_forest(df, contamination=CONTAMINATION, random_state=RANDOM_STATE):
    """Train IsolationForest on account features. Returns model, scaler, scores."""
    X = df[FEATURE_COLS].copy()
    # Handle extreme inflow_outflow_ratio (cap at 99th percentile to avoid skew)
    # Keep original for explainability, but cap for training
    X_train = X.copy()
    # Simple capping for ratio
    cap = X_train["inflow_outflow_ratio"].quantile(0.99)
    X_train["inflow_outflow_ratio"] = X_train["inflow_outflow_ratio"].clip(upper=cap)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_train)

    model = IsolationForest(
        contamination=contamination,
        random_state=random_state,
        n_estimators=150,
        max_samples="auto"
    )
    model.fit(X_scaled)
    # decision_function: higher = more normal; score_samples: opposite of anomaly score
    # We invert so higher = more anomalous
    raw_scores = -model.decision_function(X_scaled)  # higher = more anomalous
    # Normalize to 0-100 via min-max (anomaly interpretation)
    min_s, max_s = raw_scores.min(), raw_scores.max()
    if max_s - min_s < 1e-9:
        normed = np.zeros_like(raw_scores)
    else:
        normed = (raw_scores - min_s) / (max_s - min_s) * 100.0
    return model, scaler, raw_scores, normed

def score_accounts(df, contamination=CONTAMINATION):
    _, _, raw, normed = train_isolation_forest(df, contamination)
    out = pd.DataFrame({
        "account_id": df["account_id"],
        "ml_raw": raw,
        "ml_score": np.round(normed, 2)
    })
    return out

if __name__ == "__main__":
    from features import extract_features_from_db
    df = extract_features_from_db()
    scores = score_accounts(df)
    print(scores.sort_values("ml_score", ascending=False).head(10).to_string(index=False))
    print(f"Mean ml_score: {scores.ml_score.mean():.2f}, max: {scores.ml_score.max():.2f}")
    # Show overlap with synthetic labels for debugging (not used in training)
    import psycopg, os
    from dotenv import load_dotenv
    load_dotenv()
    DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/muleguard")
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM accounts WHERE id LIKE 'M%'")
            mule_ids = {r[0] for r in cur.fetchall()}
    scores["is_mule_label"] = scores["account_id"].apply(lambda x: 1 if x in mule_ids else 0)
    print(scores[scores.is_mule_label==1].sort_values("ml_score", ascending=False).head(10).to_string(index=False))
