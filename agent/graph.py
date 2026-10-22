"""LangGraph ReAct agent (Academy module-1 style) with MCP tools + HITL.

Graph shape (same idea as the calculator agent notebook):

    START → assistant ⇄ tools → END

- assistant: model node (LLM + bound tools)
- tools: ToolNode that executes tool calls
- tools_condition: conditional edge — route to tools if the model requested
  a tool call, otherwise END
- edge tools → assistant: loop that returns ToolMessages to the model

Email sends pause inside send_email via langgraph.types.interrupt until the
caller resumes with Command(resume=...).
"""

from __future__ import annotations

from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agent.llm import build_llm

SYSTEM_PROMPT = """You are an MTR news email agent.

When the user asks for the latest Hong Kong MTR accident / incident report:
1. Call web_search with a focused query (e.g. "Hong Kong MTR accident" plus a recent year/month).
2. From the returned results, pick the most recent relevant report. Prefer results that clearly describe an MTR accident/incident over generic MTR news.
3. Draft a short factual summary using ONLY information present in the search titles/snippets/URLs. Include the incident date only if it is explicitly stated; never invent details; never treat a publication/crawl date as the incident date unless the snippet says so.
4. Include source title(s) and URL(s) in the email body.
5. Call send_email with to, subject, and body. A human must approve before sending.
6. After send_email returns, report its actual status (sent / dry_run / cancelled / error) to the user.

If the user already provided a recipient address, use it. Otherwise ask for one before calling send_email.
Do not claim an email was sent unless the tool status says so.
"""


def build_agent(tools: list[BaseTool]):
    """Compile the assistant⇄tools graph with a memory checkpointer (required for interrupts)."""
    llm = build_llm()
    llm_with_tools = llm.bind_tools(tools)

    sys_msg = SystemMessage(content=SYSTEM_PROMPT)

    def assistant(state: MessagesState):
        """Model node: reason and optionally emit tool calls."""
        response = llm_with_tools.invoke([sys_msg] + state["messages"])
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("assistant", assistant)
    builder.add_node("tools", ToolNode(tools))

    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", tools_condition)
    builder.add_edge("tools", "assistant")

    # MemorySaver persists thread state so interrupt()/Command(resume=...) works.
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)
