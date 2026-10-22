"""Independently test the send_email MCP tool (defaults to dry-run)."""

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
    to = sys.argv[1] if len(sys.argv) > 1 else "test@example.com"
    async with MCPAdapter(mcp_config()) as adapter:
        tools = await adapter.list_tools()
        send = next(t for t in tools if t.name.endswith("send_email") or t.name == "send_email")
        print("Calling", send.name)
        raw = await send.ainvoke(
            {
                "to": to,
                "subject": "[TEST] MTR email tool dry-run",
                "body": "This is a test body from scripts/test_email.py.\nSource: https://example.com",
            }
        )
        print(raw if isinstance(raw, str) else json.dumps(raw, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
