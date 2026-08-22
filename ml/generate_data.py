"""
MuleGuard synthetic transaction generator
Generates normal + controlled mule patterns (fan-in, fan-out, rapid drain, chain, circular)
Seeded for reproducibility. Labels are for evaluation only - IsolationForest must NOT use them.
"""
import random, csv, os
from datetime import datetime, timedelta, timezone

RANDOM_SEED = 42
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic")

# Counts tuned for laptop-friendly size but meaningful features
N_NORMAL_ACCOUNTS = 400
N_MULE_ACCOUNTS = 25
NORMAL_TX_COUNT = 5000

# Pattern allocation (25 mule accounts total)
# A: fan-in 5, B: fan-out 5, C: rapid drain 5, D: chain 5 groups, E: circular 5 groups
N_FAN_IN = 5
N_FAN_OUT = 5
N_RAPID_DRAIN = 5
N_CHAIN_GROUPS = 5
N_CIRCULAR_GROUPS = 5

random.seed(RANDOM_SEED)

def gen_accounts():
    accounts = []
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # normal accounts C0001 - C0400
    for i in range(1, N_NORMAL_ACCOUNTS + 1):
        aid = f"C{i:04d}"
        accounts.append((aid, f"Account {aid}", "personal", base + timedelta(days=random.randint(0,30))))
    # mule accounts M0001 - M0025
    for i in range(1, N_MULE_ACCOUNTS + 1):
        aid = f"M{i:04d}"
        accounts.append((aid, f"Mule {aid}", "personal", base + timedelta(days=random.randint(0,5))))
    return accounts

def random_normal_tx(accounts_normal, txn_id_start, start_time, n):
    txs = []
    tid = txn_id_start
    normal_ids = [a[0] for a in accounts_normal]
    for _ in range(n):
        src, dst = random.sample(normal_ids, 2)
        amt = round(random.uniform(100, 5000),2)
        ts = start_time + timedelta(
            days=random.randint(0,29),
            hours=random.randint(0,23),
            minutes=random.randint(0,59)
        )
        txs.append((f"T{tid:06d}", src, dst, amt, ts, "TRANSFER", 0))
        tid += 1
    return txs, tid

def pattern_fan_in(mule_ids, pool_ids, tid, base_time):
    """Many unique senders -> one mule, within short window"""
    txs=[]
    for idx, mule in enumerate(mule_ids[:N_FAN_IN]):
        n_senders = random.randint(12,18)
        senders = random.sample(pool_ids, n_senders)
        window_start = base_time + timedelta(days=random.randint(5,20), hours=random.randint(0,12))
        for s in senders:
            amt = round(random.uniform(800, 3000),2)
            # all within 2 hours
            ts = window_start + timedelta(minutes=random.randint(0,120))
            txs.append((f"T{tid:06d}", s, mule, amt, ts, "TRANSFER", 1))
            tid+=1
    return txs, tid

def pattern_fan_out(mule_ids, pool_ids, tid, base_time):
    txs=[]
    for mule in mule_ids[N_FAN_IN:N_FAN_IN+N_FAN_OUT]:
        n_receivers = random.randint(10,15)
        receivers = random.sample(pool_ids, n_receivers)
        # mule needs inflow first (from random normal) then fan out
        inflow_amt = round(random.uniform(15000, 30000),2)
        inflow_src = random.choice(pool_ids)
        inflow_ts = base_time + timedelta(days=random.randint(5,20), hours=random.randint(0,12))
        txs.append((f"T{tid:06d}", inflow_src, mule, inflow_amt, inflow_ts, "TRANSFER", 1))
        tid+=1
        for r in receivers:
            amt = round(inflow_amt / n_receivers * random.uniform(0.85, 1.05),2)
            ts = inflow_ts + timedelta(minutes=random.randint(5, 180))
            txs.append((f"T{tid:06d}", mule, r, amt, ts, "TRANSFER", 1))
            tid+=1
    return txs, tid

def pattern_rapid_drain(mule_ids, pool_ids, tid, base_time):
    txs=[]
    for mule in mule_ids[N_FAN_IN+N_FAN_OUT:N_FAN_IN+N_FAN_OUT+N_RAPID_DRAIN]:
        inflow_src = random.choice(pool_ids)
        inflow_amt = round(random.uniform(8000, 20000),2)
        inflow_ts = base_time + timedelta(days=random.randint(5,20))
        txs.append((f"T{tid:06d}", inflow_src, mule, inflow_amt, inflow_ts, "TRANSFER", 1))
        tid+=1
        # drain 90-98% within 10 minutes to 1-3 accounts
        drain_total = inflow_amt * random.uniform(0.90, 0.98)
        n_out = random.randint(1,3)
        for i in range(n_out):
            dst = random.choice(pool_ids)
            amt = round(drain_total / n_out * random.uniform(0.9,1.1),2)
            ts = inflow_ts + timedelta(minutes=random.randint(1,10), seconds=random.randint(0,59))
            txs.append((f"T{tid:06d}", mule, dst, amt, ts, "TRANSFER", 1))
            tid+=1
    return txs, tid

def pattern_chains(mule_ids, pool_ids, tid, base_time):
    """A -> B -> C -> D layering chain, time-ordered, slight amount decay"""
    txs=[]
    # need chain groups: each chain uses 4 accounts (mix of mules + intermediaries)
    # We will create dedicated intermediary accounts? Reuse pool + mules
    # For each group, pick 4 distinct mule/pool mix
    chain_mules_start = N_FAN_IN+N_FAN_OUT+N_RAPID_DRAIN
    available = mule_ids[chain_mules_start:chain_mules_start+N_CHAIN_GROUPS*2] + random.sample(pool_ids, N_CHAIN_GROUPS*2)
    # Actually simpler: each chain is 4 hops using 1 mule as start + 3 pooled
    for i in range(N_CHAIN_GROUPS):
        chain = [mule_ids[chain_mules_start + i] if chain_mules_start+i < len(mule_ids) else random.choice(pool_ids)]
        # fill to 4
        extras = random.sample(pool_ids, 3)
        chain.extend(extras)
        # ensure 4 unique
        chain = list(dict.fromkeys(chain))[:4]
        while len(chain) < 4:
            c = random.choice(pool_ids)
            if c not in chain:
                chain.append(c)
        ts = base_time + timedelta(days=random.randint(5,22), hours=random.randint(0,20))
        amt = round(random.uniform(10000, 25000),2)
        for j in range(len(chain)-1):
            src, dst = chain[j], chain[j+1]
            # decay 1-5%
            amt = round(amt * random.uniform(0.95, 0.99),2)
            ts = ts + timedelta(minutes=random.randint(2,30))
            label = 1  # chain is suspicious
            txs.append((f"T{tid:06d}", src, dst, amt, ts, "TRANSFER", label))
            tid+=1
    return txs, tid

def pattern_circular(mule_ids, pool_ids, tid, base_time):
    txs=[]
    # Each circular: A->B->C->A
    start_idx = N_FAN_IN+N_FAN_OUT+N_RAPID_DRAIN+N_CHAIN_GROUPS
    for i in range(N_CIRCULAR_GROUPS):
        # pick 3 accounts (one mule + 2 pool)
        hub = mule_ids[start_idx + i] if start_idx+i < len(mule_ids) else random.choice(pool_ids)
        b, c = random.sample(pool_ids, 2)
        cycle = [hub, b, c]
        ts = base_time + timedelta(days=random.randint(5,22))
        amt = round(random.uniform(5000, 15000),2)
        # A->B
        txs.append((f"T{tid:06d}", cycle[0], cycle[1], amt, ts, "TRANSFER", 1)); tid+=1
        # B->C
        ts2 = ts + timedelta(minutes=random.randint(2,20))
        amt2 = round(amt*random.uniform(0.96,0.99),2)
        txs.append((f"T{tid:06d}", cycle[1], cycle[2], amt2, ts2, "TRANSFER", 1)); tid+=1
        # C->A
        ts3 = ts2 + timedelta(minutes=random.randint(2,20))
        amt3 = round(amt2*random.uniform(0.96,0.99),2)
        txs.append((f"T{tid:06d}", cycle[2], cycle[0], amt3, ts3, "TRANSFER", 1)); tid+=1
    return txs, tid

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    accounts = gen_accounts()
    normal_accounts = [a for a in accounts if a[0].startswith("C")]
    mule_accounts = [a for a in accounts if a[0].startswith("M")]
    mule_ids = [a[0] for a in mule_accounts]
    pool_ids = [a[0] for a in normal_accounts]
    base_time = datetime(2026,1,1, tzinfo=timezone.utc)

    txs, tid = random_normal_tx(normal_accounts, 1, base_time, NORMAL_TX_COUNT)
    # add mule patterns
    for fn in [pattern_fan_in, pattern_fan_out, pattern_rapid_drain, pattern_chains, pattern_circular]:
        chunk, tid = fn(mule_ids, pool_ids, tid, base_time)
        txs.extend(chunk)

    random.shuffle(txs)  # shuffle final order but timestamps remain ordered per pattern

    # Write accounts.csv
    ap = os.path.join(OUTPUT_DIR, "accounts.csv")
    with open(ap, "w", newline="", encoding="utf-8") as f:
        w=csv.writer(f)
        w.writerow(["id","name","type","created_at"])
        for r in accounts:
            w.writerow([r[0], r[1], r[2], r[3].isoformat()])

    # Write transactions.csv
    tp = os.path.join(OUTPUT_DIR, "transactions.csv")
    with open(tp, "w", newline="", encoding="utf-8") as f:
        w=csv.writer(f)
        w.writerow(["id","from_account","to_account","amount","timestamp","type","is_fraud_label"])
        for r in txs:
            w.writerow([r[0], r[1], r[2], r[3], r[4].isoformat(), r[5], r[6]])

    print(f"Seed: {RANDOM_SEED}")
    print(f"Accounts generated: {len(accounts)} (normal={len(normal_accounts)}, mule={len(mule_accounts)})")
    print(f"Transactions generated: {len(txs)} (normal~{NORMAL_TX_COUNT}, mule_patterns={len(txs)-NORMAL_TX_COUNT})")
    print(f"Synthetic mule accounts: {len(mule_accounts)}")
    print(f"Wrote {ap}")
    print(f"Wrote {tp}")

if __name__ == "__main__":
    main()

