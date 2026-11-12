"""SQLite database for users and per-user document analysis history."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "docreview.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                score INTEGER NOT NULL,
                word_count INTEGER NOT NULL,
                pages INTEGER NOT NULL,
                ocr_used INTEGER NOT NULL DEFAULT 0,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_analyses_user ON analyses(user_id, created_at DESC);
            """
        )


def create_user(name: str, email: str, password_hash: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (name.strip(), email.strip().lower(), password_hash, now),
        )
        user_id = cur.lastrowid
    return {"id": user_id, "name": name.strip(), "email": email.strip().lower(), "created_at": now}


def get_user_by_email(email: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def save_analysis(user_id: int, report: dict) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO analyses (user_id, filename, score, word_count, pages, ocr_used, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                report["filename"],
                int(report["score"]),
                int(report["wordCount"]),
                int(report["pages"]),
                1 if report.get("ocrUsed") else 0,
                json.dumps(report),
                now,
            ),
        )
        return cur.lastrowid


def list_user_analyses(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, filename, score, word_count, pages, ocr_used, created_at
            FROM analyses
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_user_analysis(user_id: int, analysis_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM analyses WHERE id = ? AND user_id = ?",
            (analysis_id, user_id),
        ).fetchone()
    if not row:
        return None
    data = json.loads(row["result_json"])
    data["id"] = row["id"]
    data["createdAt"] = row["created_at"]
    return data


def delete_user_analysis(user_id: int, analysis_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM analyses WHERE id = ? AND user_id = ?",
            (analysis_id, user_id),
        )
        return cur.rowcount > 0
