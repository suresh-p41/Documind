import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "documind.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    stored_path     TEXT NOT NULL,

    -- queued -> processing -> completed | failed
    status          TEXT NOT NULL DEFAULT 'queued',
    error           TEXT,
    result_json     TEXT,

    -- none | needs_review | approved | rejected
    review_status   TEXT NOT NULL DEFAULT 'none',
    -- JSON list of {"code", "message", "source": "manual" | "rule"}
    review_reasons  TEXT,

    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    started_at      TEXT,
    finished_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_files_batch ON files(batch_id);
CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);
CREATE INDEX IF NOT EXISTS idx_files_review ON files(review_status);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Columns added after the first release. init_db() adds any that are
# missing, so an existing database is upgraded without losing data.
MIGRATIONS = {
    "files": {
        "review_note": "TEXT",
        "reviewed_at": "TEXT",
        # JSON: page_count, ocr_score, min_page_ocr_score, low_quality_pages, empty_pages
        "ocr_quality": "TEXT",
        # JSON from the verification pass (see schemas.ReviewSignals)
        "review_signals": "TEXT",
    },
}


def init_db() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    conn = get_connection()
    try:
        with conn:
            # WAL lets the dashboard read while the worker is writing
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)

            for table, columns in MIGRATIONS.items():
                existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
                for column, column_type in columns.items():
                    if column not in existing:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
    finally:
        conn.close()
