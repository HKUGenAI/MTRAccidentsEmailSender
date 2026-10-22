---
name: safety-awareness-pulse
description: Generates a daily workplace Safety Awareness Pulse using the same 4-level search as HKUGenAI/SafetyAwarenessPulse, then emails it only with this app's send_email tool.
triggers:
  - create safety awareness pulse
  - generate safety awareness pulse
  - safety awareness pulse
  - safety reminder
  - toolbox talk
  - weekly safety briefing
  - 每日安全警示
---

# Safety Awareness Pulse

Follow [HKUGenAI/SafetyAwarenessPulse](https://github.com/HKUGenAI/SafetyAwarenessPulse) search fallback. **Do not** use Discord or any send path from that repo. Sending, if requested, is only `send_email` in this app (human approval).

Use Hong Kong today (`Asia/Hong_Kong`) from the prompt unless the user named a date. `month_day` is `MM-DD`. Levels 1–3 must be that same calendar day (any year). Stop at the first usable workplace accident. Do not invent incidents.

## Tools (this app only)

- DB: `list_tables`, `describe_table`, `extract_rows`, `query_database` (SELECT / WITH only), `save_extract`
- Search: `web_search`
- Send: `send_email` (only if they asked to email it or named a recipient)

## 4-level fallback (stop at the first hit)

### ① Local SQLite (same MM-DD)

`list_tables` first.

- If table `events` exists: `extract_rows` with `table=events` and `month_day=MM-DD` (or `query_database` `WHERE month_day = 'MM-DD'`). If several rows, pick **one at random**. Quote original Traditional Chinese `content` — never translate it.
- Else use `extracts`: `extract_rows` with `table=extracts` and a workplace-accident `topic` filter. Only keep rows whose date is that MM-DD.

If no usable row → treat as no hits, go to ②. Do not call web yet.

### ② Labour Department press releases

One `web_search`:

- `include_domains`: `labour.gov.hk`
- `language`: `zh-hk`
- query about workplace / industrial accidents on that MM-DD, e.g. `工作意外 工業意外 工傷 {M}月{D}日 {MM-DD}` targeting https://www.labour.gov.hk/tc/major/content.php

If no workplace accident on that MM-DD → ③.

### ③ World workplace web search

One `web_search` (no domain filter):

- query: `world workplace industrial working accident on {MM-DD} in history {M}月{D}日 {M}.{D} {D} {Month} 工業意外 工作意外 工傷`
- write the date several ways in the query
- drop hits that are not that MM-DD (nearby dates, ages, years that only contain the day number)

If none → ④.

### ④ Recent construction recall (real calendar days, same year)

Not “on this day in history”. Window = last **7 calendar days** ending on the alert date (e.g. 2026-10-15 → 2026-10-08…2026-10-15).

1. If `events` exists: `extract_rows` with `iso_date_from` / `iso_date_to` on construction / 地盤 / 建築 keywords, or `query_database` on that `iso_date` range.
2. If none: `web_search` with `days_back=7`, `language=zh-hk`, query like `香港 地盤 建築 工程 工業意外 工作意外 Hong Kong construction site accident {year}`.

## After a hit

Optionally `save_extract` for hits you will reuse (topic, title, url, snippet, source).

Write the user-visible pulse in the **same language as the user query**. Chinese request → Traditional Chinese; English request → English; other languages → that language. Do not mention tool names, levels, `[HITS]`, or search steps.

```
Safety Awareness Pulse  /  安全意識速報
Date / 日期：[YYYY-MM-DD]
Place / 地點：[if known]

What happened / 發生了甚麼
- [1–3 facts from DB text or search snippets only]

Why it matters / 為何重要
- [one operational risk]

This week's reminder / 本週提醒
- [2–4 concrete actions]

Sources / 來源
- [title] [url or PPT source_file]
```

Keep it under ~250 words. Never invent.

## Email

Call `send_email` **only** if they asked to send it or named a recipient. Subject: `Safety Awareness Pulse — [topic or date]`. Body = the pulse text above. Wait for human approval. Do not claim it was sent unless the tool status says so.
