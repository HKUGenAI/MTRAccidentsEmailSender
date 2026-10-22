"""Independently test SQLite extraction MCP tools (no LLM)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.mcp_tools import mcp_config  # noqa: E402
from langchain.mcp import MCPAdapter  # noqa: E402


def _print(raw: object) -> None:
    print(raw if isinstance(raw, str) else json.dumps(raw, indent=2, ensure_ascii=False))


def _by_suffix(tools: list, suffix: str):
    return next(t for t in tools if t.name.endswith(suffix) or t.name == suffix)


async def main() -> None:
    load_dotenv(ROOT / ".env")
    topic = " ".join(sys.argv[1:]) or "safety"
    async with MCPAdapter(mcp_config()) as adapter:
        tools = await adapter.list_tools()
        print("Loaded:", [t.name for t in tools])

        save = _by_suffix(tools, "save_extract")
        tables = _by_suffix(tools, "list_tables")
        describe = _by_suffix(tools, "describe_table")
        extract = _by_suffix(tools, "extract_rows")
        query = _by_suffix(tools, "query_database")

        print("\n--- save_extract ---")
        _print(
            await save.ainvoke(
                {
                    "topic": topic,
                    "title": "Sample extract",
                    "url": "https://example.com",
                    "snippet": "Fixture row for scripts/test_db.py",
                    "source": "test",
                    "published_at": "",
                }
            )
        )
        print("\n--- list_tables ---")
        _print(await tables.ainvoke({}))
        print("\n--- describe_table ---")
        _print(await describe.ainvoke({"table": "extracts"}))
        print("\n--- extract_rows ---")
        _print(await extract.ainvoke({"table": "extracts", "topic": topic, "limit": 5}))
        print("\n--- query_database ---")
        _print(
            await query.ainvoke(
                {
                    "sql": "SELECT id, topic, title FROM extracts ORDER BY id DESC LIMIT 5",
                    "max_rows": 5,
                }
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
