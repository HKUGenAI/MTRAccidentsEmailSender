"""LangGraph ReAct agent: general tool-using graph.

    START → assistant ⇄ tools → END

MCP tools and skill tools are bound at compile time. Skills are optional tools:
the model decides whether to call one; the tool returns a multi-step playbook.
"""

from __future__ import annotations

from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agent.llm import build_llm

SYSTEM_PROMPT = """You are a general tool-using agent. Pick tools from what is bound
to you based on the user's task. Do not assume Hong Kong MTR or any other topic
unless they asked for it.

Write the user-visible answer in the same language as the user's request
(Chinese → Traditional Chinese, English → English, etc.). Do not default to a
language they did not use.

Typical tools:
- web_search: latest news / web facts (snippets only; never invent details)
- list_tables, describe_table, query_database, extract_rows: read the SQLite database
- save_extract: store a search hit for later
- send_email: draft/send email; a human must approve; report the tool status
- use_*: skills. Each is a playbook with many instructions. Call it only when
  the user actually wants that kind of task. After it returns, follow that
  playbook with the other tools. Do not call a skill for a normal search/email.

How to choose:
- Need facts from the web → web_search
- Need stored records → list_tables then extract_rows or query_database (SELECT only)
- Need to email someone → send_email after you have the body
- Need a named skill's workflow → call that use_* tool first, then follow it

If they named a recipient, use it. Otherwise ask before send_email.
Do not claim an email was sent unless the tool status says so.
"""


def _tool_catalog(tools: list[BaseTool]) -> str:
    lines = ["Bound tools:"]
    for tool in tools:
        desc = (getattr(tool, "description", None) or "").split("\n", 1)[0].strip()
        lines.append(f"- {tool.name}" + (f": {desc}" if desc else ""))
    return "\n".join(lines)


def build_system_prompt(tools: list[BaseTool], user_request: str = "") -> str:
    del user_request  # kept for callers; skills are tools, not prompt injection
    return "\n\n".join([SYSTEM_PROMPT, _tool_catalog(tools)])


def build_agent(tools: list[BaseTool], user_request: str = ""):
    """Compile the assistant⇄tools graph with a memory checkpointer (required for interrupts)."""
    llm = build_llm()
    llm_with_tools = llm.bind_tools(tools)
    sys_msg = SystemMessage(content=build_system_prompt(tools, user_request))

    def assistant(state: MessagesState):
        response = llm_with_tools.invoke([sys_msg] + state["messages"])
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("assistant", assistant)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", tools_condition)
    builder.add_edge("tools", "assistant")
    return builder.compile(checkpointer=MemorySaver())
