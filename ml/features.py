import os
import pandas as pd
from pathlib import Path
import psycopg
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/muleguard")

FEATURE_COLS = [
    "total_in","total_out","cnt_in","cnt_out","unique_senders","unique_receivers",
    "avg_amount","max_amount","tx_count","inflow_outflow_ratio","fan_in_score",
    "fan_out_score","activity_duration_hours","velocity_per_hour"
]

def extract_features_from_db():
    """Aggregate account-level features. Handles zero-division safely."""
    sql = "SELECT id AS account_id FROM accounts"
    with psycopg.connect(DB_URL) as conn:
        accounts = pd.read_sql(sql, conn)
        tx = pd.read_sql("SELECT from_account, to_account, amount, timestamp FROM transactions", conn)
        tx["timestamp"] = pd.to_datetime(tx["timestamp"], utc=True)
    if tx.empty:
        raise ValueError("No transactions found")
    tx["amount"] = tx["amount"].astype(float)
    rows = []
    for aid in accounts["account_id"]:
        incoming = tx[tx["to_account"] == aid]
        outgoing = tx[tx["from_account"] == aid]
        total_in = float(incoming["amount"].sum()) if not incoming.empty else 0.0
        total_out = float(outgoing["amount"].sum()) if not outgoing.empty else 0.0
        cnt_in = int(len(incoming))
        cnt_out = int(len(outgoing))
        unique_senders = int(incoming["from_account"].nunique()) if not incoming.empty else 0
        unique_receivers = int(outgoing["to_account"].nunique()) if not outgoing.empty else 0
        all_amounts = pd.concat([incoming["amount"], outgoing["amount"]]) if not incoming.empty or not outgoing.empty else pd.Series(dtype=float)
        avg_amount = float(all_amounts.mean()) if not all_amounts.empty else 0.0
        max_amount = float(all_amounts.max()) if not all_amounts.empty else 0.0
        tx_count = cnt_in + cnt_out
        inflow_outflow_ratio = float(total_in / total_out) if total_out > 0 else (float(total_in) if total_in > 0 else 0.0)
        fan_in_score = unique_senders
        fan_out_score = unique_receivers
        times = pd.concat([incoming["timestamp"], outgoing["timestamp"]]) if not incoming.empty or not outgoing.empty else pd.Series(dtype="datetime64[ns, UTC]")
        if not times.empty and times.nunique() > 1:
            duration_h = (times.max() - times.min()).total_seconds() / 3600.0
            duration_h = max(duration_h, 0.01)
        else:
            duration_h = 0.0
        velocity = float(tx_count / duration_h) if duration_h > 0 else float(tx_count)
        rows.append({
            "account_id": aid,
            "total_in": round(total_in,2),
            "total_out": round(total_out,2),
            "cnt_in": cnt_in,
            "cnt_out": cnt_out,
            "unique_senders": unique_senders,
            "unique_receivers": unique_receivers,
            "avg_amount": round(avg_amount,2),
            "max_amount": round(max_amount,2),
            "tx_count": tx_count,
            "inflow_outflow_ratio": round(inflow_outflow_ratio,4),
            "fan_in_score": fan_in_score,
            "fan_out_score": fan_out_score,
            "activity_duration_hours": round(float(duration_h),2),
            "velocity_per_hour": round(float(velocity),4)
        })
    df = pd.DataFrame(rows)
    return df

def save_features(df, to_db=True, csv_path=None):
    if csv_path is None:
        csv_path = Path(__file__).parent.parent / "data" / "processed" / "features.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    print(f"Features saved to {csv_path} ({len(df)} accounts)")
    if to_db:
        with psycopg.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM account_features")
                for _, row in df.iterrows():
                    cur.execute("""
                        INSERT INTO account_features
                        (account_id, total_in, total_out, cnt_in, cnt_out, unique_senders, unique_receivers,
                         avg_amount, max_amount, tx_count, inflow_outflow_ratio, fan_in_score, fan_out_score,
                         activity_duration_hours, velocity_per_hour)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, tuple(row[col] for col in ["account_id"] + FEATURE_COLS))
            conn.commit()
        print(f"Features persisted to account_features ({len(df)} rows)")

if __name__ == "__main__":
    df = extract_features_from_db()
    print(df.head().to_string())
    print(df.describe().to_string())
    save_features(df)
