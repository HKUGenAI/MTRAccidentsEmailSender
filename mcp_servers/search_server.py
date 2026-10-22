"""MCP server: web_search tool (titles, URLs, snippets).

Follows the MCP "build a server" pattern — expose tools over stdio.
Uses DuckDuckGo by default; switches to Serper when SERPER_API_KEY is set.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

# STDIO servers must never print to stdout — logging goes to stderr.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("search_server")

mcp = MCPServer("web-search")

SERPER_SEARCH_URL = "https://google.serper.dev/search"
SERPER_NEWS_URL = "https://google.serper.dev/news"
USER_AGENT = "news-email-agent/1.0"


def _search_locale() -> tuple[str, str, str]:
    """(ddgs region, serper gl, serper hl) from SEARCH_REGION / SEARCH_GL / SEARCH_HL."""
    region = (os.getenv("SEARCH_REGION") or "wt-wt").strip() or "wt-wt"
    gl = (os.getenv("SEARCH_GL") or "us").strip() or "us"
    hl = (os.getenv("SEARCH_HL") or "en").strip() or "en"
    return region, gl, hl


def _serper_search(query: str, max_results: int) -> list[dict[str, str]]:
    api_key = (os.getenv("SERPER_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("SERPER_API_KEY is not set")

    _, gl, hl = _search_locale()
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": query, "num": max_results, "gl": gl, "hl": hl}
    results: list[dict[str, str]] = []

    with httpx.Client(timeout=30.0) as client:
        # Prefer news endpoint; fall back to organic search.
        news_resp = client.post(SERPER_NEWS_URL, headers=headers, json=payload)
        if news_resp.status_code == 200:
            for item in news_resp.json().get("news", [])[:max_results]:
                results.append(
                    {
                        "title": item.get("title") or "",
                        "url": item.get("link") or "",
                        "snippet": item.get("snippet") or item.get("date") or "",
                        "date": item.get("date") or "",
                        "source": item.get("source") or "serper-news",
                    }
                )

        if len(results) < max_results:
            search_resp = client.post(SERPER_SEARCH_URL, headers=headers, json=payload)
            search_resp.raise_for_status()
            for item in search_resp.json().get("organic", []):
                if len(results) >= max_results:
                    break
                results.append(
                    {
                        "title": item.get("title") or "",
                        "url": item.get("link") or "",
                        "snippet": item.get("snippet") or "",
                        "date": item.get("date") or "",
                        "source": "serper-web",
                    }
                )

    return results


def _ddg_search(query: str, max_results: int) -> list[dict[str, str]]:
    try:
        from ddgs import DDGS
    except ImportError:  # pragma: no cover
        from duckduckgo_search import DDGS  # type: ignore

    region, _, _ = _search_locale()
    results: list[dict[str, str]] = []
    with DDGS() as ddgs:
        # Prefer news hits, then fill with web text results.
        try:
            for item in ddgs.news(query, max_results=max_results, region=region):
                results.append(
                    {
                        "title": item.get("title") or "",
                        "url": item.get("url") or item.get("href") or "",
                        "snippet": item.get("body") or item.get("excerpt") or "",
                        "date": item.get("date") or "",
                        "source": item.get("source") or "duckduckgo-news",
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ddgs.news failed (%s); falling back to text search", exc)

        if len(results) < max_results:
            for item in ddgs.text(query, max_results=max_results, region=region):
                if len(results) >= max_results:
                    break
                url = item.get("href") or item.get("link") or ""
                if any(url and url == existing["url"] for existing in results):
                    continue
                results.append(
                    {
                        "title": item.get("title") or "",
                        "url": url,
                        "snippet": item.get("body") or item.get("snippet") or "",
                        "date": "",
                        "source": "duckduckgo",
                    }
                )
    return results[:max_results]


def _run_search(query: str, max_results: int) -> list[dict[str, str]]:
    max_results = max(1, min(int(max_results), 10))
    if (os.getenv("SERPER_API_KEY") or "").strip():
        logger.info("Searching via Serper: %s", query)
        return _serper_search(query, max_results)
    logger.info("Searching via DuckDuckGo: %s", query)
    return _ddg_search(query, max_results)


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return result titles, URLs, and snippets.

    Use this for recent news lookups on whatever topic the user named.
    Returns JSON only — do not invent details beyond these snippets.

    Args:
        query: Search query string.
        max_results: Maximum number of results (1–10). Defaults to 5.
    """
    try:
        hits = _run_search(query, max_results)
    except Exception as exc:  # noqa: BLE001 — surface tool errors to the model
        logger.exception("web_search failed")
        return json.dumps({"ok": False, "error": str(exc), "results": []})

    payload: dict[str, Any] = {
        "ok": True,
        "query": query,
        "count": len(hits),
        "results": hits,
        "note": (
            "Snippets may include publication dates. Do not invent an incident date "
            "if it is not stated, and do not confuse publication date with incident date."
        ),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
