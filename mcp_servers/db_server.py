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


_MONTH_DAY_RE = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
_ISO_DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


@mcp.tool()
def extract_rows(
    table: str,
    topic: str = "",
    limit: int = 20,
    month_day: str = "",
    iso_date_from: str = "",
    iso_date_to: str = "",
) -> str:
    """Extract recent rows from a table as JSON (basic dump / filter).

    For `extracts`, pass topic to filter. For `events` (SafetyAwarenessPulse
    schema), pass month_day (MM-DD) and/or iso_date_from / iso_date_to.

    Args:
        table: Table to read.
        topic: Optional topic filter (topic/title/content LIKE %topic%).
        limit: Maximum rows (1–200). Defaults to 20.
        month_day: Optional MM-DD (events.month_day exact match).
        iso_date_from: Optional YYYY-MM-DD lower bound (iso_date column).
        iso_date_to: Optional YYYY-MM-DD upper bound (iso_date column).
    """
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table or ""):
        return _err("Invalid table name.")
    limit = max(1, min(int(limit), 200))
    month_day = (month_day or "").strip()
    iso_from = (iso_date_from or "").strip()
    iso_to = (iso_date_to or "").strip()
    if month_day and not _MONTH_DAY_RE.match(month_day):
        return _err("month_day must be MM-DD.")
    if iso_from and not _ISO_DATE_RE.match(iso_from):
        return _err("iso_date_from must be YYYY-MM-DD.")
    if iso_to and not _ISO_DATE_RE.match(iso_to):
        return _err("iso_date_to must be YYYY-MM-DD.")
    try:
        with _connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if not exists:
                return _err(f"No table named {table!r}.")
            cols = [c["name"] for c in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            clauses: list[str] = []
            params: list[Any] = []
            if topic:
                like = f"%{topic}%"
                like_cols = [c for c in ("topic", "title", "content", "snippet") if c in cols]
                if like_cols:
                    clauses.append(
                        "(" + " OR ".join(f"{c} LIKE ?" for c in like_cols) + ")"
                    )
                    params.extend([like] * len(like_cols))
            if month_day:
                if "month_day" not in cols:
                    return _err(f"Table {table!r} has no month_day column.")
                clauses.append("month_day = ?")
                params.append(month_day)
            if iso_from or iso_to:
                if "iso_date" not in cols:
                    return _err(f"Table {table!r} has no iso_date column.")
                if iso_from:
                    clauses.append("iso_date >= ?")
                    params.append(iso_from)
                if iso_to:
                    clauses.append("iso_date <= ?")
                    params.append(iso_to)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            if "iso_date" in cols:
                order = "ORDER BY iso_date DESC, id DESC" if "id" in cols else "ORDER BY iso_date DESC"
            elif "id" in cols:
                order = "ORDER BY id DESC"
            else:
                order = ""
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
