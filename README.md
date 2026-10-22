# Tool-using agent (search, database, email, skills)

LangGraph + MCP agent. The graph is the same for every task; **tools** and **skills** decide what it does.

- Tools: `web_search`, SQLite read/extract (`list_tables`, `describe_table`, `query_database`, `extract_rows`, `save_extract`), `send_email` (human approval)
- Skills: markdown playbooks in `agent/skills/`, each bound as a `use_*` tool. The model decides whether to call one (same as any other tool); the tool returns the full playbook.
- Topic is whatever you pass in (not hardcoded to MTR)

Based on:

- [LangChain Academy Agent notebook](https://colab.research.google.com/github/langchain-ai/langchain-academy/blob/main/module-1/agent.ipynb)
- [Build an MCP server](https://modelcontextprotocol.io/docs/2026-07-28/develop/build-server)
- [LangChain MCPAdapter](https://docs.langchain.com/oss/python/langchain/mcp)
- [smtplib](https://docs.python.org/3/library/smtplib.html)
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)

MCP server layout follows [BachelorOogway/MTRAccidentsEmailSender](https://github.com/BachelorOogway/MTRAccidentsEmailSender).

## Setup

macOS / Linux:

```bash
cd agent/MTRAccidentsEmailSender
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set AZURE_OPENAI_API_KEY. Keep EMAIL_DRY_RUN=true at first.
```

Windows:

```powershell
cd d:\RA\MTRAccidentsEmailSender
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Edit .env: set AZURE_OPENAI_API_KEY. Keep EMAIL_DRY_RUN=true at first.
```

## Run

macOS / Linux:

```bash
# Part 1 — calculator ReAct loop (local tools, no MCP)
python -m examples.calculator_agent

# Part 2 — test search MCP tool alone
python scripts/test_search.py "Hong Kong restaurant hygiene"

# Part 3 — test email MCP tool alone (dry-run by default)
python scripts/test_email.py you@example.com

# Part 3b — test SQLite extraction tools
python scripts/test_db.py safety

# Part 4 — full agent (pauses for y/N before send)
python -m agent.main --topic "Hong Kong restaurant inspections" --to you@example.com
python -m agent.main -q "create safety awareness pulse for depot staff and email it to you@example.com"
python scripts/test_skills.py
```

Windows:

```powershell
# Part 1 — calculator ReAct loop (local tools, no MCP)
python -m examples.calculator_agent

# Part 2 — test search MCP tool alone
python scripts\test_search.py "Hong Kong restaurant hygiene"

# Part 3 — test email MCP tool alone (dry-run by default)
python scripts\test_email.py you@example.com

# Part 3b — test SQLite extraction tools
python scripts\test_db.py safety

# Part 4 — full agent (will pause for y/N before send)
python -m agent.main --topic "Hong Kong restaurant inspections" --to you@example.com
python -m agent.main -q "create safety awareness pulse for depot staff and email it to you@example.com"
python scripts\test_skills.py
```

## Project layout

| Path | Role |
|------|------|
| `examples/calculator_agent.py` | Academy-style model⇄tools loop |
| `mcp_servers/search_server.py` | MCP `web_search` |
| `mcp_servers/email_server.py` | MCP `send_email` (SMTP / dry-run) |
| `mcp_servers/db_server.py` | MCP `list_tables`, `describe_table`, `query_database`, `extract_rows`, `save_extract` |
| `agent/mcp_tools.py` | `MCPAdapter` load (session stays open) + interrupt wrapper |
| `agent/graph.py` | LangGraph `assistant` ⇄ `tools` (MCP + skill tools) |
| `agent/skills.py` | Load `agent/skills/*/SKILL.md` as optional `use_*` tools |
| `agent/skills/safety-awareness-pulse/` | Runtime skill: create a safety awareness pulse |
| `agent/main.py` | CLI + `Command(resume=...)` approval loop |

## Architecture (short)

```
User request
    │
    └─ LangGraph  START → assistant ⇄ tools → END
                      │
                      ├─ use_* skill tools (optional playbooks; model chooses)
                      ├─ web_search
                      ├─ list_tables / describe_table / query_database / extract_rows / save_extract
                      └─ send_email (interrupt until y/N)
```

SMTP credentials stay in `.env` (`SMTP_*`). `EMAIL_DRY_RUN=true` returns the draft without sending.

SQLite path is `DB_PATH` or `data/extracts.db`. Search locale is `SEARCH_REGION` / `SEARCH_GL` / `SEARCH_HL` (worldwide by default).
