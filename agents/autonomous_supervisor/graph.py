"""Autonomous supervisor: a deepagents-based central orchestrator whose
sub-agents are remote graphs, not in-process callables.

`deepagents.create_deep_agent` delegates to sub-agents via a `task` tool
(an LLM-driven decision, not a fixed pipeline) -- a different mechanism from
LangGraph's structural subgraphs (see agents/subgraph_demo), so it does NOT
get stream_subgraphs/interrupt_before-style control over its sub-agents.
What it does get: `deepagents.middleware.subagents.CompiledSubAgent.runnable`
accepts anything that satisfies `Runnable`, and `RemoteGraph` does -- so each
remote agent is registered directly, with no wrapper tool/function needed.
The LLM autonomously decides which remote agent(s) to call and in what order.
"""

from __future__ import annotations

import os

import httpx
from deepagents import create_deep_agent
from deepagents.middleware.subagents import CompiledSubAgent
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.pregel.remote import RemoteGraph
from langgraph_sdk import get_sync_client
from pydantic import SecretStr

load_dotenv()

DEFAULT_BASE_URL = "http://localhost:2026"

# A deep agent's own reasoning, plus each task-tool delegation re-entering a
# full remote ReAct loop on a small local model, chains several sequential
# LLM calls. langgraph_sdk's own default (read=300s) is already generous,
# but an explicit float here would *replace* it with a flat (and lower)
# value for every leg, not just read -- use httpx.Timeout so only read grows.
REMOTE_READ_TIMEOUT = httpx.Timeout(connect=10, read=600, write=600, pool=10)


def _remote(assistant_id: str) -> RemoteGraph:
    env_var = f"{assistant_id.upper()}_URL"
    base_url = os.environ.get(env_var) or os.environ.get("REMOTEGRAPH_BASE_URL") or DEFAULT_BASE_URL
    sync_client = get_sync_client(
        url=base_url,
        timeout=REMOTE_READ_TIMEOUT,  # ty: ignore[invalid-argument-type] -- stub is narrower than the documented runtime behavior (httpx.Timeout is accepted)
    )
    return RemoteGraph(assistant_id, url=base_url, sync_client=sync_client)


def _get_chat_model() -> ChatOpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        api_key=SecretStr(api_key) if api_key else None,
        base_url=os.environ.get("OPENAI_BASE_URL") or None,
    )


subagents = [
    CompiledSubAgent(
        name="researcher",
        description=(
            "Searches the web for up-to-date information. Use for any research, "
            "fact-finding, or background-gathering subtask."
        ),
        runnable=_remote("researcher"),
    ),
    CompiledSubAgent(
        name="coder",
        description=(
            "Writes and executes Python code to solve a well-specified programming "
            "subtask. Returns the code and its output."
        ),
        runnable=_remote("coder"),
    ),
    CompiledSubAgent(
        name="reviewer",
        description=(
            "Reviews a piece of Python code for correctness and style using ruff. "
            "Use after code has been written, before finalizing an answer."
        ),
        runnable=_remote("reviewer"),
    ),
]

graph = create_deep_agent(
    model=_get_chat_model(),
    tools=[],
    subagents=subagents,
    system_prompt=(
        "You are an autonomous supervisor. You have no tools of your own -- "
        "delegate to the researcher/coder/reviewer sub-agents via the task tool "
        "to accomplish the user's request, deciding yourself which ones to use, "
        "in what order, and whether to use more than one. For coding tasks, "
        "prefer: research relevant background if needed, write the code, then "
        "have it reviewed before giving your final answer."
    ),
)
