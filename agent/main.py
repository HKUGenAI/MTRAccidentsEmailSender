"""CLI entry: run the news email agent with human email approval."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from agent.graph import build_agent
from agent.mcp_tools import mcp_tools
from agent.skills import matching_skills


def _interrupt_payload(result: dict[str, Any]) -> Any | None:
    """Extract the first interrupt value from an invoke() result."""
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0]
    return getattr(first, "value", first)


def _print_messages(result: dict[str, Any]) -> None:
    for msg in result.get("messages", []):
        role = getattr(msg, "type", msg.__class__.__name__)
        content = getattr(msg, "content", "")
        tool_calls = getattr(msg, "tool_calls", None)
        print(f"\n[{role}]")
        if content:
            print(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, indent=2))
        if tool_calls:
            print("tool_calls:", json.dumps(tool_calls, ensure_ascii=False, indent=2))


def _ask_approval(payload: Any) -> bool:
    print("\n" + "=" * 60)
    print("EMAIL DRAFT — human approval required")
    print("=" * 60)
    if isinstance(payload, dict):
        print(f"To:      {payload.get('to', '')}")
        print(f"Subject: {payload.get('subject', '')}")
        print("-" * 60)
        print(payload.get("body", ""))
    else:
        print(payload)
    print("=" * 60)
    answer = input("Approve send? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


async def run_once(user_request: str, thread_id: str | None = None) -> None:
    active = matching_skills(user_request)
    if active:
        print("Active skills:", [s.name for s in active])

    # Adapter must stay open while the graph calls tools (stdio MCP sessions).
    async with mcp_tools() as tools:
        print("Loaded tools:", [t.name for t in tools])
        graph = build_agent(tools, user_request=user_request)
        config = {"configurable": {"thread_id": thread_id or str(uuid.uuid4())}}

        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=user_request)]},
            config=config,
        )

        while True:
            payload = _interrupt_payload(result)
            if payload is None:
                break
            approved = _ask_approval(payload)
            result = await graph.ainvoke(Command(resume=approved), config=config)

        print("\n----- final -----")
        _print_messages(result)
        last = result["messages"][-1]
        print("\nAssistant:", getattr(last, "content", last))


def build_default_request(to: str | None, topic: str | None) -> str:
    recipient = to or "my specified recipient (ask me for the address if needed)"
    if topic:
        return (
            f"Find the latest reported news about {topic} and email a short summary "
            f"to {recipient}."
        )
    return (
        "Find the latest reported news on the topic named in this message and email "
        f"a short summary to {recipient}. If no topic is named, ask me for one "
        "before you search."
    )


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="News email agent (LangGraph + MCP)")
    parser.add_argument(
        "-q",
        "--query",
        default=None,
        help="Full user request. Overrides --topic.",
    )
    parser.add_argument(
        "--topic",
        default=None,
        help='News topic, e.g. "Hong Kong restaurant hygiene" or "Hong Kong MTR accident".',
    )
    parser.add_argument(
        "--to",
        default=None,
        help="Recipient email address to include in the default request.",
    )
    parser.add_argument(
        "--thread-id",
        default=None,
        help="Optional thread id for checkpoint/resume.",
    )
    args = parser.parse_args()

    request = args.query or build_default_request(args.to, args.topic)
    print("Request:", request)
    asyncio.run(run_once(request, thread_id=args.thread_id))


if __name__ == "__main__":
    main()
