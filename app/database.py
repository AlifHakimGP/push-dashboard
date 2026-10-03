"""
database.py — a thin wrapper around SQLite.

WHY PLAIN sqlite3 INSTEAD OF AN ORM (SQLAlchemy, SQLModel, etc.)
------------------------------------------------------------------
An ORM is genuinely useful once a project's data model grows, but for a
single table with five columns, hand-writing the SQL is actually clearer
to learn from — you see exactly what's happening, with no "magic" layer
translating Python objects into queries behind the scenes.

WHY SQLITE INSTEAD OF POSTGRES
--------------------------------
This keeps the whole app a true single-container monolith: the database
is just a file inside the container, no second `db` service needed (unlike
the local-stack project). That's the deliberate trade-off here — fine for
a personal dashboard, not what you'd reach for with real concurrent load.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "pushes.db"


def get_connection() -> sqlite3.Connection:
    """
    Open a fresh connection for one request.

    SQLite connections aren't meant to be shared across threads by
    default, so rather than keeping one long-lived connection around, we
    just open a lightweight one per call. `row_factory` makes rows behave
    like dicts (row["repo"]) instead of plain tuples (row[0]) — much
    easier to read and to convert into JSON.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the pushes table if it doesn't already exist."""
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pushes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo TEXT NOT NULL,
            branch TEXT NOT NULL,
            commit_sha TEXT NOT NULL,
            commit_message TEXT NOT NULL,
            author TEXT NOT NULL,
            pushed_at TEXT NOT NULL,
            received_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'received'
        )
        """
    )
    conn.commit()
    conn.close()


def insert_push(repo, branch, commit_sha, commit_message, author, pushed_at, received_at) -> int:
    conn = get_connection()
    cur = conn.execute(
        """
        INSERT INTO pushes (repo, branch, commit_sha, commit_message, author, pushed_at, received_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'received')
        """,
        (repo, branch, commit_sha, commit_message, author, pushed_at, received_at),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def list_pushes(limit=50, offset=0, repo=None, branch=None, status=None):
    conn = get_connection()
    query = "SELECT * FROM pushes WHERE 1=1"
    params = []
    if repo:
        query += " AND repo = ?"
        params.append(repo)
    if branch:
        query += " AND branch = ?"
        params.append(branch)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_push(push_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM pushes WHERE id = ?", (push_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_status(push_id: int, status: str) -> bool:
    conn = get_connection()
    cur = conn.execute("UPDATE pushes SET status = ? WHERE id = ?", (status, push_id))
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated
