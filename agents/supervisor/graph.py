"""Supervisor agent: orchestrates researcher/coder/reviewer via RemoteGraph.

This is the agent that "uses the collection of agents" — it never imports
their graphs directly. It connects to whichever backend currently hosts them
(REMOTEGRAPH_BASE_URL) through LangGraph's RemoteGraph client, the same way it
would talk to LangGraph Platform Cloud.
"""

from __future__ import annotations

import os
from typing import TypedDict

from langgraph.graph import StateGraph
from langgraph.pregel.remote import RemoteGraph


def _remote(assistant_id: str) -> RemoteGraph:
    base_url = os.environ.get("REMOTEGRAPH_BASE_URL", "http://localhost:2026")
    return RemoteGraph(assistant_id, url=base_url)


class SupervisorState(TypedDict):
    task: str
    research: str
    code: str
    review: str


def research_node(state: SupervisorState) -> dict:
    result = _remote("researcher").invoke(
        {"messages": [{"role": "user", "content": state["task"]}]}
    )
    return {"research": result["messages"][-1]["content"]}


def code_node(state: SupervisorState) -> dict:
    prompt = (
        f"Task: {state['task']}\n\nResearch notes:\n{state['research']}\n\n"
        "Write Python code that accomplishes the task."
    )
    result = _remote("coder").invoke({"messages": [{"role": "user", "content": prompt}]})
    return {"code": result["messages"][-1]["content"]}


def review_node(state: SupervisorState) -> dict:
    prompt = f"Review the following code for correctness and style:\n\n{state['code']}"
    result = _remote("reviewer").invoke({"messages": [{"role": "user", "content": prompt}]})
    return {"review": result["messages"][-1]["content"]}


graph = (
    StateGraph(SupervisorState)  # ty: ignore[invalid-argument-type] -- known ty false positive on TypedDict vs StateT bound
    .add_node("research", research_node)
    .add_node("code", code_node)
    .add_node("review", review_node)
    .add_edge("__start__", "research")
    .add_edge("research", "code")
    .add_edge("code", "review")
    .add_edge("review", "__end__")
    .compile()
)
