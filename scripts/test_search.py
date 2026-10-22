"""Independently test the web_search MCP tool (no LLM)."""

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


async def main() -> None:
    load_dotenv(ROOT / ".env")
    query = " ".join(sys.argv[1:]) or "Hong Kong MTR accident 2025"
    async with MCPAdapter(mcp_config()) as adapter:
        tools = await adapter.list_tools()
        search = next(t for t in tools if t.name.endswith("web_search"))
        print("Calling", search.name, "query=", query)
        raw = await search.ainvoke({"query": query, "max_results": 5})
        print(raw if isinstance(raw, str) else json.dumps(raw, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
