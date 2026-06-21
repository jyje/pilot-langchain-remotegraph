"""Subgraph demo: a deterministic, LLM-free graph with an actual subgraph node.

Exists to verify, against a real backend, that RemoteGraph's
`stream_subgraphs` and `interrupt_before` work against a node that is itself
a compiled subgraph -- not just a plain function node. researcher/coder/
reviewer are flat ReAct agents and can't exercise this path.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class InnerState(TypedDict):
    text: str


def shout(state: InnerState) -> dict:
    return {"text": state["text"].upper()}


inner_graph = (
    StateGraph(InnerState)  # ty: ignore[invalid-argument-type] -- known ty false positive on TypedDict vs StateT bound
    .add_node("shout", shout)
    .add_edge(START, "shout")
    .add_edge("shout", END)
    .compile()
)


class OuterState(TypedDict):
    text: str


def prepare(state: OuterState) -> dict:
    return {"text": f"[prepared] {state['text']}"}


def finalize(state: OuterState) -> dict:
    return {"text": f"{state['text']} [finalized]"}


graph = (
    StateGraph(OuterState)  # ty: ignore[invalid-argument-type] -- known ty false positive on TypedDict vs StateT bound
    .add_node("prepare", prepare)
    .add_node("inner", inner_graph)
    .add_node("finalize", finalize)
    .add_edge(START, "prepare")
    .add_edge("prepare", "inner")
    .add_edge("inner", "finalize")
    .add_edge("finalize", END)
    .compile()
)
