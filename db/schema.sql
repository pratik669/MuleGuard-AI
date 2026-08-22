-- MuleGuard - PostgreSQL schema (MVP)
-- Run: psql -U postgres -d muleguard -f db/schema.sql
-- Idempotent: safe to re-run

CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'personal',
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    from_account TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    to_account TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    timestamp TIMESTAMPTZ NOT NULL,
    type TEXT NOT NULL DEFAULT 'TRANSFER',
    is_fraud_label INT NOT NULL DEFAULT 0 CHECK (is_fraud_label IN (0,1))
);

CREATE INDEX IF NOT EXISTS idx_tx_from ON transactions(from_account);
CREATE INDEX IF NOT EXISTS idx_tx_to ON transactions(to_account);
CREATE INDEX IF NOT EXISTS idx_tx_timestamp ON transactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_tx_from_to ON transactions(from_account, to_account);

-- Account-level features materialized from transactions
CREATE TABLE IF NOT EXISTS account_features (
    account_id TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    total_in NUMERIC(14,2) NOT NULL DEFAULT 0,
    total_out NUMERIC(14,2) NOT NULL DEFAULT 0,
    cnt_in INT NOT NULL DEFAULT 0,
    cnt_out INT NOT NULL DEFAULT 0,
    unique_senders INT NOT NULL DEFAULT 0,
    unique_receivers INT NOT NULL DEFAULT 0,
    avg_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    max_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    tx_count INT NOT NULL DEFAULT 0,
    inflow_outflow_ratio NUMERIC(10,4) NOT NULL DEFAULT 0,
    fan_in_score INT NOT NULL DEFAULT 0,
    fan_out_score INT NOT NULL DEFAULT 0,
    activity_duration_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    velocity_per_hour NUMERIC(10,4) NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Risk scores: ML + rules (+ graph later)
CREATE TABLE IF NOT EXISTS risk_scores (
    account_id TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    ml_score NUMERIC(5,2) NOT NULL CHECK (ml_score >= 0 AND ml_score <= 100),
    rule_score NUMERIC(5,2) NOT NULL CHECK (rule_score >= 0 AND rule_score <= 100),
    graph_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (graph_score >= 0 AND graph_score <= 100),
    final_score NUMERIC(5,2) NOT NULL CHECK (final_score >= 0 AND final_score <= 100),
    risk_level TEXT NOT NULL CHECK (risk_level IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_final_score ON risk_scores(final_score DESC);
CREATE INDEX IF NOT EXISTS idx_risk_level ON risk_scores(risk_level);

