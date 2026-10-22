"""Build a chat model from Azure OpenAI environment variables."""

from __future__ import annotations

import os

from langchain_openai import AzureChatOpenAI


def build_llm():
    """Return a tool-calling Azure OpenAI chat model."""
    azure_key = (os.getenv("AZURE_OPENAI_API_KEY") or "").strip()
    endpoint = (os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip()
    deployment = (os.getenv("AZURE_OPENAI_DEPLOYMENT") or "gpt-5.4-mini").strip()
    api_version = (os.getenv("AZURE_OPENAI_API_VERSION") or "2024-12-01-preview").strip()

    if not azure_key or not endpoint:
        raise RuntimeError(
            "Set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT in .env "
            "(see .env.example)."
        )

    return AzureChatOpenAI(
        azure_endpoint=endpoint.rstrip("/") + "/",
        azure_deployment=deployment,
        api_version=api_version,
        api_key=azure_key,
        max_tokens=16384,
    )
