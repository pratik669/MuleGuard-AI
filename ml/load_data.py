import os, csv, sys
from pathlib import Path
import psycopg
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/muleguard")
SYN_DIR = Path(__file__).parent.parent / "data" / "synthetic"
SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"

def get_conn():
    return psycopg.connect(DB_URL)

def apply_schema():
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print("Schema applied from db/schema.sql")

def load_csv():
    acc_path = SYN_DIR / "accounts.csv"
    tx_path = SYN_DIR / "transactions.csv"
    if not acc_path.exists() or not tx_path.exists():
        print(f"Missing {acc_path} or {tx_path} - run ml/generate_data.py first")
        sys.exit(1)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM risk_scores")
            cur.execute("DELETE FROM account_features")
            cur.execute("DELETE FROM transactions")
            cur.execute("DELETE FROM accounts")
            with open(acc_path, newline="", encoding="utf-8") as f:
                r = csv.DictReader(f)
                rows = list(r)
                for row in rows:
                    cur.execute("INSERT INTO accounts (id, name, type, created_at) VALUES (%s,%s,%s,%s)", (row["id"], row["name"], row["type"], row["created_at"]))
            print(f"Accounts loaded: {len(rows)}")
            with open(tx_path, newline="", encoding="utf-8") as f:
                r = csv.DictReader(f)
                rows = list(r)
                for row in rows:
                    cur.execute("INSERT INTO transactions (id, from_account, to_account, amount, timestamp, type, is_fraud_label) VALUES (%s,%s,%s,%s,%s,%s,%s)", (row["id"], row["from_account"], row["to_account"], row["amount"], row["timestamp"], row["type"], int(row["is_fraud_label"])))
            cur.execute("SELECT COUNT(*) FROM transactions WHERE is_fraud_label=1")
            mule_tx = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM accounts WHERE id LIKE 'M%'")
            mule_acc = cur.fetchone()[0]
            print(f"Transactions loaded: {len(rows)} (mule-labelled tx: {mule_tx})")
            print(f"Synthetic mule accounts: {mule_acc}")
            cur.execute("SELECT COUNT(*) FROM accounts")
            print(f"Total accounts in DB: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM transactions")
            print(f"Total transactions in DB: {cur.fetchone()[0]}")
        conn.commit()

if __name__ == "__main__":
    apply_schema()
    load_csv()
