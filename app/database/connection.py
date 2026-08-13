"""SQLite connection management and schema creation for Brain OS.

Facility 3 (Knowledge Memory): every workflow's invoices, risk
assessments, approvals, briefings, and audit trail live here. The schema
is created automatically on startup -- there is no separate migration
step for this MVP.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    workflow_id TEXT PRIMARY KEY,
    vendor TEXT,
    po_number TEXT,
    amount REAL,
    raw_text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_assessments (
    workflow_id TEXT PRIMARY KEY,
    risk_score REAL NOT NULL,
    auto_approved INTEGER NOT NULL,
    anomalies_json TEXT NOT NULL,
    threshold REAL NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES invoices (workflow_id)
);

CREATE TABLE IF NOT EXISTS approvals (
    workflow_id TEXT PRIMARY KEY,
    decision TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    note TEXT,
    decided_at TEXT NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES invoices (workflow_id)
);

CREATE TABLE IF NOT EXISTS briefings (
    workflow_id TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    generated_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES invoices (workflow_id)
);

CREATE TABLE IF NOT EXISTS workflow_state (
    workflow_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES invoices (workflow_id)
);

-- No foreign key here on purpose: the audit trail must be able to record
-- a workflow.start event before the invoice row exists, and must never
-- fail to log because of referential integrity.
CREATE TABLE IF NOT EXISTS audit_trail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_trail_workflow_id ON audit_trail (workflow_id);
"""


def init_schema(database_path: str) -> None:
    """Create the database file and all tables if they do not already exist."""
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def get_connection(database_path: str) -> Iterator[sqlite3.Connection]:
    """Yield a short-lived SQLite connection with row access by column name.

    A fresh connection per call keeps this safe to use from FastAPI's
    threadpool-executed sync request handlers without sharing a single
    connection object across threads.
    """
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
