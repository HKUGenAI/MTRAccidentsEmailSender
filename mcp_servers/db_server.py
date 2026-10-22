"""MCP server: basic SQLite extraction tools.

Same stdio MCPServer pattern as search_server.py / email_server.py in
https://github.com/BachelorOogway/MTRAccidentsEmailSender

Tools are read-oriented. query_database only accepts SELECT / WITH.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db_server")

mcp = MCPServer("database")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "extracts.db"

_WRITE_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM)\b",
    re.IGNORECASE,
)


def _db_path() -> Path:
    raw = (os.getenv("DB_PATH") or "").strip()
    path = Path(raw).expanduser() if raw else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS extracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL DEFAULT '',
            snippet TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            published_at TEXT NOT NULL DEFAULT '',
            extracted_at TEXT NOT NULL,
            extra_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_extracts_topic ON extracts(topic)"
    )
    conn.commit()


def _ok(payload: dict[str, Any]) -> str:
    return json.dumps({"ok": True, **payload}, ensure_ascii=False, indent=2)


def _err(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False, indent=2)


@mcp.tool()
def list_tables() -> str:
    """List tables in the local SQLite database (DB_PATH)."""
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        return _ok({"db": str(_db_path()), "tables": [r["name"] for r in rows]})
    except Exception as exc:  # noqa: BLE001
        logger.exception("list_tables failed")
        return _err(str(exc))


@mcp.tool()
def describe_table(table: str) -> str:
    """Return column names and types for one table.

    Args:
        table: Table name (letters, numbers, underscore only).
    """
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table or ""):
        return _err("Invalid table name.")
    try:
        with _connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if not exists:
                return _err(f"No table named {table!r}.")
            cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return _ok(
            {
                "table": table,
                "columns": [
                    {
                        "cid": c["cid"],
                        "name": c["name"],
                        "type": c["type"],
                        "notnull": bool(c["notnull"]),
                        "pk": bool(c["pk"]),
                    }
                    for c in cols
                ],
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("describe_table failed")
        return _err(str(exc))


@mcp.tool()
def query_database(sql: str, max_rows: int = 50) -> str:
    """Run a read-only SELECT (or WITH ... SELECT) and return rows as JSON.

    Args:
        sql: SELECT statement only. Writes are rejected.
        max_rows: Maximum rows to return (1–200). Defaults to 50.
    """
    stripped = (sql or "").strip().rstrip(";")
    if not stripped:
        return _err("sql is empty.")
    if _WRITE_RE.search(stripped):
        return _err("Only SELECT / WITH queries are allowed.")
    if not re.match(r"^(SELECT|WITH)\b", stripped, re.IGNORECASE):
        return _err("Query must start with SELECT or WITH.")
    limit = max(1, min(int(max_rows), 200))
    try:
        with _connect() as conn:
            cur = conn.execute(stripped)
            rows = cur.fetchmany(limit)
            columns = [d[0] for d in cur.description] if cur.description else []
        return _ok(
            {
                "columns": columns,
                "count": len(rows),
                "rows": [dict(r) for r in rows],
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("query_database failed")
        return _err(str(exc))


@mcp.tool()
def extract_rows(table: str, topic: str = "", limit: int = 20) -> str:
    """Extract recent rows from a table as JSON (basic dump / filter).

    For the default `extracts` table, pass topic to filter. For other tables,
    returns the latest rows up to limit.

    Args:
        table: Table to read.
        topic: Optional topic filter (extracts.topic LIKE %topic%).
        limit: Maximum rows (1–200). Defaults to 20.
    """
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table or ""):
        return _err("Invalid table name.")
    limit = max(1, min(int(limit), 200))
    try:
        with _connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if not exists:
                return _err(f"No table named {table!r}.")
            cols = [c["name"] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            params: list[Any] = []
            where = ""
            if topic and "topic" in cols:
                where = "WHERE topic LIKE ?"
                params.append(f"%{topic}%")
            order = "ORDER BY id DESC" if "id" in cols else ""
            sql = f"SELECT * FROM {table} {where} {order} LIMIT {limit}"
            rows = conn.execute(sql, params).fetchall()
        return _ok({"table": table, "count": len(rows), "rows": [dict(r) for r in rows]})
    except Exception as exc:  # noqa: BLE001
        logger.exception("extract_rows failed")
        return _err(str(exc))


@mcp.tool()
def save_extract(
    topic: str,
    title: str,
    url: str = "",
    snippet: str = "",
    source: str = "",
    published_at: str = "",
) -> str:
    """Save one search hit into extracts so later pulses can reuse it.

    Args:
        topic: User topic (e.g. restaurant hygiene, MTR incident).
        title: Result title.
        url: Source URL.
        snippet: Short text from search.
        source: Publisher or search backend.
        published_at: Date string if known.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO extracts (topic, title, url, snippet, source, published_at, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (topic, title, url, snippet, source, published_at, now),
            )
            conn.commit()
            row_id = cur.lastrowid
        return _ok({"id": row_id, "topic": topic, "title": title})
    except Exception as exc:  # noqa: BLE001
        logger.exception("save_extract failed")
        return _err(str(exc))


if __name__ == "__main__":
    mcp.run(transport="stdio")
