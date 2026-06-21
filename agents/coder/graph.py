"""Coder agent: writes and executes Python code for a given task."""

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
def run_python(code: str) -> str:
    """Execute a snippet of Python code in an isolated subprocess and return its stdout/stderr."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        path = Path(f.name)
    try:
        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        return output or "(no output)"
    finally:
        path.unlink(missing_ok=True)


graph = create_agent(
    _get_chat_model(),
    tools=[run_python],
    system_prompt=(
        "You are a coding agent. Write correct, minimal Python and use the "
        "run_python tool to verify it actually runs before giving your final answer."
    ),
)
