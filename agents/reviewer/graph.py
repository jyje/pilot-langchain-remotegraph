"""Reviewer agent: lints and critiques code produced by the coder agent."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

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
def lint_python(code: str) -> str:
    """Run ruff against a snippet of Python code and return the lint findings."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        path = Path(f.name)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() or "No issues found."
    finally:
        path.unlink(missing_ok=True)


graph = create_agent(
    _get_chat_model(),
    tools=[lint_python],
    system_prompt=(
        "You are a code review agent. Use the lint_python tool to check submitted "
        "code and give a concise verdict plus any issues found."
    ),
)
