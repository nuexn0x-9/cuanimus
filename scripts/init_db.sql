-- ==============================================================================
-- CUANIMUS Quantitative Relational Database Initialization Schema
-- PostgreSQL Schema for Trading Telemetry, Orders, Audit Logs, and Agent States
-- ==============================================================================

CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    pair VARCHAR(32) NOT NULL,
    is_open BOOLEAN NOT NULL DEFAULT FALSE,
    fee_open NUMERIC(16, 8) DEFAULT 0,
    fee_close NUMERIC(16, 8) DEFAULT 0,
    open_rate NUMERIC(20, 8) NOT NULL,
    close_rate NUMERIC(20, 8),
    amount NUMERIC(20, 8) NOT NULL,
    stake_amount NUMERIC(20, 8) NOT NULL,
    open_date TIMESTAMP WITH TIME ZONE NOT NULL,
    close_date TIMESTAMP WITH TIME ZONE,
    open_order_id VARCHAR(64),
    stop_loss NUMERIC(20, 8),
    initial_stop_loss NUMERIC(20, 8),
    max_rate NUMERIC(20, 8),
    min_rate NUMERIC(20, 8),
    exit_reason VARCHAR(64),
    exit_order_status VARCHAR(32),
    close_profit NUMERIC(10, 6),
    close_profit_abs NUMERIC(20, 8),
    strategy VARCHAR(64) NOT NULL,
    timeframe VARCHAR(16) DEFAULT '15m',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trades_pair ON trades(pair);
CREATE INDEX IF NOT EXISTS idx_trades_is_open ON trades(is_open);
CREATE INDEX IF NOT EXISTS idx_trades_open_date ON trades(open_date);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    ft_trade_id INTEGER REFERENCES trades(id) ON DELETE SET NULL,
    ft_order_side VARCHAR(16) NOT NULL,
    ft_pair VARCHAR(32) NOT NULL,
    ft_is_open BOOLEAN NOT NULL DEFAULT TRUE,
    ft_amount NUMERIC(20, 8) NOT NULL,
    ft_price NUMERIC(20, 8) NOT NULL,
    order_id VARCHAR(64) UNIQUE,
    status VARCHAR(32) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    order_type VARCHAR(16) NOT NULL,
    side VARCHAR(16) NOT NULL,
    price NUMERIC(20, 8),
    average NUMERIC(20, 8),
    amount NUMERIC(20, 8),
    filled NUMERIC(20, 8),
    remaining NUMERIC(20, 8),
    cost NUMERIC(20, 8),
    order_date TIMESTAMP WITH TIME ZONE NOT NULL,
    order_filled_date TIMESTAMP WITH TIME ZONE,
    order_update_date TIMESTAMP WITH TIME ZONE,
    ft_fee_base NUMERIC(16, 8) DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_trade_id ON orders(ft_trade_id);

CREATE TABLE IF NOT EXISTS wallet_history (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    currency VARCHAR(16) NOT NULL DEFAULT 'USDT',
    balance NUMERIC(20, 8) NOT NULL,
    available NUMERIC(20, 8) NOT NULL,
    locked NUMERIC(20, 8) DEFAULT 0,
    is_live BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_wallet_timestamp ON wallet_history(timestamp);

CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    agent_id VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    mode VARCHAR(32) NOT NULL DEFAULT 'paper',
    risk_profile VARCHAR(32) NOT NULL DEFAULT 'balanced',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    agent_id VARCHAR(64) NOT NULL,
    action VARCHAR(64) NOT NULL,
    domain VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    details JSONB,
    signature VARCHAR(128)
);

CREATE INDEX IF NOT EXISTS idx_audit_agent ON audit_logs(agent_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
