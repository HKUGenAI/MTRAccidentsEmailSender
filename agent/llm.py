"""Build a chat model from environment (OpenAI or Azure OpenAI)."""

from __future__ import annotations

import os

from langchain_openai import AzureChatOpenAI, ChatOpenAI


def _looks_like_azure_key(key: str) -> bool:
    """Azure OpenAI keys are often long and end with a region/resource marker."""
    return "ACOGl" in key or key.endswith("Qy") and len(key) > 80


def build_llm():
    """Return a tool-calling chat model.

    Prefer Azure when AZURE_OPENAI_API_KEY is set; otherwise use OPENAI_API_KEY.
    In Hong Kong / mainland China, platform.openai.com is often blocked (403
    unsupported_country_region_territory) — use Azure instead.
    """
    azure_key = (os.getenv("AZURE_OPENAI_API_KEY") or "").strip()
    if azure_key:
        endpoint = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").rstrip("/") + "/"
        deployment = (os.getenv("AZURE_OPENAI_DEPLOYMENT") or "").strip()
        api_version = (os.getenv("AZURE_OPENAI_API_VERSION") or "2024-12-01-preview").strip()
        if not endpoint.strip("/") or not deployment:
            raise RuntimeError(
                "Azure OpenAI selected but AZURE_OPENAI_ENDPOINT / "
                "AZURE_OPENAI_DEPLOYMENT is missing."
            )
        return AzureChatOpenAI(
            azure_endpoint=endpoint,
            azure_deployment=deployment,
            api_version=api_version,
            api_key=azure_key,
            temperature=0,
        )

    openai_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not openai_key:
        raise RuntimeError(
            "Set AZURE_OPENAI_API_KEY (+ ENDPOINT + DEPLOYMENT) or OPENAI_API_KEY "
            "in .env (see .env.example). In HK/CN prefer Azure OpenAI."
        )

    if _looks_like_azure_key(openai_key) or (
        os.getenv("AZURE_OPENAI_ENDPOINT") or ""
    ).strip():
        raise RuntimeError(
            "OPENAI_API_KEY looks like an Azure key (or AZURE_OPENAI_ENDPOINT is set). "
            "Move the key to AZURE_OPENAI_API_KEY and set AZURE_OPENAI_ENDPOINT + "
            "AZURE_OPENAI_DEPLOYMENT. Do not use OPENAI_API_KEY for Azure credentials."
        )

    model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
    return ChatOpenAI(model=model, temperature=0, api_key=openai_key)
