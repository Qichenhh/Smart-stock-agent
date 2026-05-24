-- Memory 模块 SQLite Schema
-- usage: sqlite3 memory_data/memory.db < memory_schema.sql

CREATE TABLE IF NOT EXISTS analysis_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'default',
    symbol TEXT NOT NULL,
    name TEXT DEFAULT '',
    analyzed_at TEXT NOT NULL,
    task_type TEXT DEFAULT 'comprehensive',
    rating TEXT DEFAULT '',
    tech_score INTEGER DEFAULT 50,
    fund_score INTEGER DEFAULT 50,
    senti_score INTEGER DEFAULT 50,
    total_score INTEGER DEFAULT 0,
    summary TEXT DEFAULT '',
    key_risks TEXT DEFAULT '[]',
    key_factors TEXT DEFAULT '[]',
    report_id TEXT DEFAULT '',
    importance REAL DEFAULT 0.5,
    merged_count INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_ah_symbol ON analysis_history(symbol);
CREATE INDEX IF NOT EXISTS idx_ah_analyzed ON analysis_history(analyzed_at);

CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'default',
    category TEXT NOT NULL,
    value TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    confidence REAL DEFAULT 0.5,
    last_updated TEXT DEFAULT (datetime('now')),
    source TEXT DEFAULT 'inferred',
    UNIQUE(user_id, category, value)
);

CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'default',
    symbol TEXT NOT NULL,
    name TEXT DEFAULT '',
    market TEXT DEFAULT 'A',
    added_at TEXT DEFAULT (datetime('now')),
    reason TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    alert_enabled INTEGER DEFAULT 0,
    last_price REAL DEFAULT 0,
    last_viewed_at TEXT DEFAULT '',
    UNIQUE(user_id, symbol)
);
