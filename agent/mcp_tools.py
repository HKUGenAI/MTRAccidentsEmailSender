"""Load MCP tools and wrap send_email with a LangGraph interrupt for approval."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from langchain.mcp import MCPAdapter
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import interrupt
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
SEARCH_SERVER = ROOT / "mcp_servers" / "search_server.py"
EMAIL_SERVER = ROOT / "mcp_servers" / "email_server.py"


def mcp_config() -> dict[str, Any]:
    """Stdio MCP config pointing at the two local servers."""
    python = sys.executable
    return {
        "mcpServers": {
            "search": {
                "command": python,
                "args": [str(SEARCH_SERVER)],
            },
            "email": {
                "command": python,
                "args": [str(EMAIL_SERVER)],
            },
        }
    }


def _tool_name(tool: BaseTool) -> str:
    return (getattr(tool, "name", None) or "").lower()


def _base_tool_name(tool: BaseTool) -> str:
    """Strip MCPConfig server prefix (`search_web_search` → `web_search`)."""
    name = getattr(tool, "name", "") or ""
    for prefix in ("search_", "email_"):
        if name.startswith(prefix) and name != prefix.rstrip("_"):
            return name[len(prefix) :]
    return name


def _is_send_email_tool(tool: BaseTool) -> bool:
    return _base_tool_name(tool) == "send_email" or _tool_name(tool).endswith(
        "send_email"
    )


class SendEmailInput(BaseModel):
    to: str = Field(description="Recipient email address")
    subject: str = Field(description="Email subject line")
    body: str = Field(description="Plain-text email body with summary and source links")


def wrap_send_email_with_interrupt(send_tool: BaseTool) -> StructuredTool:
    """Pause before every send so a human can approve or reject the draft.

    The interrupt payload surfaces to / subject / body. On resume, the value
    returned by interrupt() is the human decision (bool or dict with approved).
    """

    async def _arun(to: str, subject: str, body: str) -> str:
        decision = interrupt(
            {
                "type": "email_approval",
                "message": "Approve sending this email?",
                "to": to,
                "subject": subject,
                "body": body,
            }
        )

        approved = False
        if isinstance(decision, bool):
            approved = decision
        elif isinstance(decision, dict):
            approved = bool(decision.get("approved", decision.get("approve", False)))
        elif isinstance(decision, str):
            approved = decision.strip().lower() in {"y", "yes", "true", "approve", "approved"}

        if not approved:
            return json.dumps(
                {
                    "ok": True,
                    "sent": False,
                    "cancelled": True,
                    "status": "Human rejected the email; nothing was sent.",
                    "to": to,
                    "subject": subject,
                },
                ensure_ascii=False,
                indent=2,
            )

        # After approval, call the real MCP send_email tool.
        if hasattr(send_tool, "ainvoke"):
            return await send_tool.ainvoke({"to": to, "subject": subject, "body": body})
        return send_tool.invoke({"to": to, "subject": subject, "body": body})

    def _run(to: str, subject: str, body: str) -> str:
        # Sync path still hits interrupt(); ToolNode prefers async when available.
        decision = interrupt(
            {
                "type": "email_approval",
                "message": "Approve sending this email?",
                "to": to,
                "subject": subject,
                "body": body,
            }
        )
        approved = False
        if isinstance(decision, bool):
            approved = decision
        elif isinstance(decision, dict):
            approved = bool(decision.get("approved", decision.get("approve", False)))
        elif isinstance(decision, str):
            approved = decision.strip().lower() in {"y", "yes", "true", "approve", "approved"}

        if not approved:
            return json.dumps(
                {
                    "ok": True,
                    "sent": False,
                    "cancelled": True,
                    "status": "Human rejected the email; nothing was sent.",
                    "to": to,
                    "subject": subject,
                },
                ensure_ascii=False,
                indent=2,
            )
        return send_tool.invoke({"to": to, "subject": subject, "body": body})

    return StructuredTool.from_function(
        name="send_email",
        description=(
            "Draft/send an email with fields to, subject, and body. "
            "ALWAYS call this when the user asks to email a summary. "
            "A human must approve before the message is actually sent. "
            "Report the tool's returned status (sent / dry_run / cancelled / error)."
        ),
        func=_run,
        coroutine=_arun,
        args_schema=SendEmailInput,
    )


async def load_mcp_tools() -> list[BaseTool]:
    """Discover MCP tools and replace send_email with an interrupt-gated wrapper."""
    async with MCPAdapter(mcp_config()) as adapter:
        tools = await adapter.list_tools()

    prepared: list[BaseTool] = []
    send_tool: BaseTool | None = None
    for tool in tools:
        if _is_send_email_tool(tool):
            send_tool = tool
            continue
        # Prefer unprefixed names in the agent prompt / tool schema.
        base = _base_tool_name(tool)
        if base and base != tool.name:
            tool.name = base
        prepared.append(tool)

    if send_tool is None:
        raise RuntimeError(
            "MCP email server did not expose send_email. "
            f"Loaded tools: {[getattr(t, 'name', t) for t in tools]}"
        )

    prepared.append(wrap_send_email_with_interrupt(send_tool))
    return prepared
