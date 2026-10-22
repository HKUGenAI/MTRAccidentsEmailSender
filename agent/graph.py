"""LangGraph ReAct agent: general tool-using graph + optional skills.

    START → assistant ⇄ tools → END

Tools (MCP) are bound at compile time. Skills are markdown playbooks injected
into the system prompt when the user request matches (e.g. "create safety
awareness pulse").
"""

from __future__ import annotations

from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agent.llm import build_llm
from agent.skills import format_skills_for_prompt

SYSTEM_PROMPT = """You are a general tool-using agent. Pick tools from what is bound
to you based on the user's task. Do not assume Hong Kong MTR or any other topic
unless they asked for it.

Typical tools:
- web_search: latest news / web facts (snippets only; never invent details)
- list_tables, describe_table, query_database, extract_rows: read the SQLite database
- save_extract: store a search hit for later
- send_email: draft/send email; a human must approve; report the tool status

How to choose:
- Need facts from the web → web_search
- Need stored records → list_tables then extract_rows or query_database (SELECT only)
- Need to email someone → send_email after you have the body
- Request matches an Active skill below → follow that skill exactly

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
    parts = [SYSTEM_PROMPT, _tool_catalog(tools)]
    skill_block = format_skills_for_prompt(user_request)
    if skill_block:
        parts.append(skill_block)
    return "\n\n".join(parts)


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
