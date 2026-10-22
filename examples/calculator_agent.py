"""Part 1 of the exercise: LangGraph Academy-style calculator agent.

Maps directly to module-1/agent.ipynb:
- assistant = model node
- tools = ToolNode
- tools_condition = conditional edge
- tools → assistant = loop that returns tool results to the model
"""

from __future__ import annotations

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agent.llm import build_llm


def multiply(a: int, b: int) -> int:
    """Multiply a and b."""
    return a * b


def add(a: int, b: int) -> int:
    """Add a and b."""
    return a + b


def divide(a: int, b: int) -> float:
    """Divide a and b."""
    return a / b


def main() -> None:
    load_dotenv()
    tools = [add, multiply, divide]
    llm = build_llm().bind_tools(tools, parallel_tool_calls=False)
    sys_msg = SystemMessage(content="You are a helpful assistant tasked with arithmetic.")

    def assistant(state: MessagesState):
        return {"messages": [llm.invoke([sys_msg] + state["messages"])]}

    builder = StateGraph(MessagesState)
    builder.add_node("assistant", assistant)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", tools_condition)
    builder.add_edge("tools", "assistant")
    graph = builder.compile()

    request = "Add 3 and 4. Multiply the sum by 12. Divide the product by 4."
    result = graph.invoke({"messages": [HumanMessage(content=request)]})
    for msg in result["messages"]:
        print(f"[{msg.type}] {msg.content or getattr(msg, 'tool_calls', '')}")


if __name__ == "__main__":
    main()
