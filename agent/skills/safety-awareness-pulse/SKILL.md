---
name: safety-awareness-pulse
description: Generates a short Safety Awareness Pulse from the database and/or web search, then optionally emails it.
triggers:
  - create safety awareness pulse
  - safety awareness pulse
  - safety reminder
  - toolbox talk
  - weekly safety briefing
---

# Safety Awareness Pulse

When the user says **create safety awareness pulse** (or a trigger above), follow this playbook. Do not assume MTR unless they named it.

## Tools

1. Read the database first: `list_tables`, then `extract_rows` on `extracts` (optional `topic` filter) or `query_database` with a SELECT.
2. If there are no useful rows, or they asked for the latest news, call `web_search`.
3. Optionally `save_extract` for hits you will reuse.
4. Call `send_email` only if they asked to send it (or named a recipient). Subject: `Safety Awareness Pulse — [topic]`. Wait for human approval.

## Output

```
SAFETY AWARENESS PULSE
Period: [dates or "this week"]
Topic: [user topic]

What happened
- [1–3 facts with source titles]

Why it matters
- [one operational risk]

This week's reminder
- [one concrete action]

Sources
- [title] [url]
```

Rules: use only facts from DB rows, search snippets, or the user. Never invent incidents. Keep it under ~200 words.
