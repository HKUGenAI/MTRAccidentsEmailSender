# MTR News Email Agent

LangGraph + MCP homework agent that:

1. Searches the web for the latest reported Hong Kong MTR accident
2. Summarizes only what appears in search results
3. Shows an email draft and waits for **human approval** (`interrupt`)
4. Sends via SMTP (or dry-run) and reports the tool status

Based on:

- [LangChain Academy Agent notebook](https://colab.research.google.com/github/langchain-ai/langchain-academy/blob/main/module-1/agent.ipynb)
- [Build an MCP server](https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server)
- [LangChain MCPAdapter](https://docs.langchain.com/oss/python/langchain/mcp)
- [smtplib](https://docs.python.org/3/library/smtplib.html)
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)

## Setup

```powershell
cd d:\RA\MTRAccidentsEmailSender
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Edit .env: set OPENAI_API_KEY (or Azure keys). Keep EMAIL_DRY_RUN=true at first.
```

## Run

```powershell
# Part 1 — calculator ReAct loop (local tools, no MCP)
python -m examples.calculator_agent

# Part 2 — test search MCP tool alone
python scripts\test_search.py "Hong Kong MTR accident"

# Part 3 — test email MCP tool alone (dry-run by default)
python scripts\test_email.py you@example.com

# Part 4 — full agent (will pause for y/N before send)
python -m agent.main --to you@example.com
```

## Project layout

| Path | Role |
|------|------|
| `examples/calculator_agent.py` | Academy-style model⇄tools loop |
| `mcp_servers/search_server.py` | MCP `web_search` |
| `mcp_servers/email_server.py` | MCP `send_email` (SMTP / dry-run) |
| `agent/mcp_tools.py` | `MCPAdapter` load + interrupt wrapper |
| `agent/graph.py` | LangGraph `assistant` / `tools` / `tools_condition` |
| `agent/main.py` | CLI + `Command(resume=...)` approval loop |

## Architecture (short)

```
User → agent/main.py
         │
         ├─ MCPAdapter(stdio) → search_server.web_search
         │                    → email_server.send_email
         │
         └─ LangGraph StateGraph (MessagesState + MemorySaver)
              START → assistant ⇄ tools → END
                       │            │
                       │            └─ send_email hits interrupt()
                       │                 until Command(resume=yes/no)
                       └─ tools_condition routes tool_calls vs END
```

SMTP credentials stay in `.env` (`SMTP_*`). `EMAIL_DRY_RUN=true` returns the draft without sending.
