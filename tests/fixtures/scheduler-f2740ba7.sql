-- Schema from ellmos-scheduler f2740ba7, version 0.3.6. No runtime data.

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    schedule_json TEXT NOT NULL,
    executor TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    generation INTEGER NOT NULL DEFAULT 1,
    next_due_at TEXT NOT NULL,
    lease_seconds INTEGER NOT NULL DEFAULT 900,
    timeout_seconds INTEGER NOT NULL DEFAULT 600,
    authorities_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id),
    scheduled_for TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    claimed_by TEXT NOT NULL,
    lease_expires_at TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    exit_code INTEGER,
    output TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    authority_receipt_json TEXT NOT NULL DEFAULT '[]',
    authority_set_sha256 TEXT,
    authority_error TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_runs_job_time ON runs(job_id, scheduled_for DESC);
CREATE TABLE IF NOT EXISTS controls (
    scope TEXT PRIMARY KEY,
    paused INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT '',
    steer_message TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
