"""SQLite storage: users, sessions, action logs."""
import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("SPICE_DB", Path(__file__).resolve().parent.parent / "spicescript.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'user',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS action_logs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER REFERENCES users(id),
    username       TEXT NOT NULL,
    action         TEXT NOT NULL,   -- login, logout, register, run_stage
    stage          TEXT,            -- lexical, syntax, semantic, icg, run, full
    status         TEXT NOT NULL,   -- success, error
    input_snapshot TEXT,
    detail         TEXT,
    created_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_logs_user ON action_logs(user_id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


# ---- passwords --------------------------------------------------------------

def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()


def verify_password(password: str, salt: str, expected: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt), expected)


# ---- users / sessions -------------------------------------------------------

def create_user(username: str, password: str):
    """The very first user becomes admin. Returns the new user row or None if taken."""
    salt = secrets.token_hex(16)
    with connect() as conn:
        is_first = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        try:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, salt, role, created_at) VALUES (?,?,?,?,?)",
                (username, hash_password(password, salt), salt, "admin" if is_first else "user", now()),
            )
        except sqlite3.IntegrityError:
            return None
        return conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()


def get_user_by_name(username: str):
    with connect() as conn:
        return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with connect() as conn:
        conn.execute("INSERT INTO sessions (token, user_id, created_at) VALUES (?,?,?)", (token, user_id, now()))
    return token


def get_user_by_token(token: str):
    with connect() as conn:
        return conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?", (token,)
        ).fetchone()


def delete_session(token: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ---- logs -------------------------------------------------------------------

def add_log(user_id, username, action, stage=None, status="success", input_snapshot=None, detail=None) -> None:
    snapshot = input_snapshot[:2000] if input_snapshot else None  # keep rows small
    with connect() as conn:
        conn.execute(
            "INSERT INTO action_logs (user_id, username, action, stage, status, input_snapshot, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (user_id, username, action, stage, status, snapshot, detail, now()),
        )


def get_logs(user_id=None, limit=200):
    """user_id=None returns everyone's logs (admin view)."""
    with connect() as conn:
        if user_id is None:
            rows = conn.execute("SELECT * FROM action_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM action_logs WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
            ).fetchall()
    return [dict(r) for r in rows]
