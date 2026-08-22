import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")

with psycopg.connect(db_url) as conn:
    rows = conn.execute("""
        SELECT
            account_id,
            final_score,
            risk_level,
            ml_score,
            rule_score,
            graph_score
        FROM risk_scores
        WHERE account_id LIKE 'M%'
        ORDER BY final_score DESC;
    """).fetchall()

print("\n===== KNOWN MULE ACCOUNT ANALYSIS =====")
print("Account | Final | Risk | ML | Rules | Graph")
print("-" * 60)

for row in rows:
    print(row)