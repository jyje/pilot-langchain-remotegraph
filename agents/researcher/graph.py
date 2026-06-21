"""Researcher agent: gathers information from the web for a given task."""

from __future__ import annotations

import os
import re

import requests
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

# Self-contained on purpose: backends load this file standalone via
# importlib, without adding the repo root to sys.path, so it can't reach a
# sibling `agents.llm` module.
load_dotenv()


def _get_chat_model() -> ChatOpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        api_key=SecretStr(api_key) if api_key else None,
        base_url=os.environ.get("OPENAI_BASE_URL") or None,
    )


@tool
def web_search(query: str) -> str:
    """Search the web via DuckDuckGo and return the top result titles and snippets."""
    response = requests.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
    )
    response.raise_for_status()
    pairs = re.findall(
        r'class="result__a"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</a>',
        response.text,
        re.DOTALL,
    )
    if not pairs:
        return "No results found."
    lines = []
    for title, snippet in pairs[:5]:
        clean_title = re.sub("<[^<]+?>", "", title).strip()
        clean_snippet = re.sub("<[^<]+?>", "", snippet).strip()
        lines.append(f"- {clean_title}: {clean_snippet}")
    return "\n".join(lines)


graph = create_agent(
    _get_chat_model(),
    tools=[web_search],
    system_prompt=(
        "You are a research agent. Use the web_search tool to gather relevant, "
        "up-to-date information for the user's task, then summarize the findings concisely."
    ),
)
