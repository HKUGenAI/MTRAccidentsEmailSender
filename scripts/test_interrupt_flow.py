"""Verify LangGraph interrupt gates send_email without calling an LLM."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.mcp_tools import wrap_send_email_with_interrupt  # noqa: E402


class _Args(BaseModel):
    to: str = Field(...)
    subject: str = Field(...)
    body: str = Field(...)


def _fake_send(to: str, subject: str, body: str) -> str:
    return json.dumps({"ok": True, "sent": True, "dry_run": False, "to": to, "status": "sent"})


async def main() -> None:
    underlying = StructuredTool.from_function(
        name="send_email_raw",
        description="raw",
        func=_fake_send,
        args_schema=_Args,
    )
    gated = wrap_send_email_with_interrupt(underlying)

    def assistant(state: MessagesState):
        # Force a single send_email tool call (no LLM).
        if any(isinstance(m, ToolMessage) for m in state["messages"]):
            return {
                "messages": [
                    AIMessage(content="Email tool finished; reporting status to user.")
                ]
            }
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "send_email",
                            "args": {
                                "to": "a@b.com",
                                "subject": "subj",
                                "body": "hello body",
                            },
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        }

    builder = StateGraph(MessagesState)
    builder.add_node("assistant", assistant)
    builder.add_node("tools", ToolNode([gated]))
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", tools_condition)
    builder.add_edge("tools", "assistant")
    graph = builder.compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "interrupt-demo"}}

    first = await graph.ainvoke(
        {"messages": [HumanMessage(content="send it")]}, config=config
    )
    assert first.get("__interrupt__"), "expected interrupt before send"
    print("interrupt payload:", first["__interrupt__"][0].value)

    resumed = await graph.ainvoke(Command(resume=True), config=config)
    tool_msgs = [m for m in resumed["messages"] if isinstance(m, ToolMessage)]
    print("tool result:", tool_msgs[-1].content)
    assert "sent" in tool_msgs[-1].content
    print("interrupt flow OK")


if __name__ == "__main__":
    asyncio.run(main())
