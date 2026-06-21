"""Node functions for the subgraph_demo workflow/subgraph-workflow (see workflow.yaml,
inner_workflow.yaml, and src/remotegraph/workflow.py)."""

from __future__ import annotations

PREPARED_PREFIX = "[prepared] "


def prepare(state: dict) -> dict:
    return {"text": f"{PREPARED_PREFIX}{state['text']}"}


def finalize(state: dict) -> dict:
    return {"text": f"{state['text']} [finalized]"}


def validate(state: dict) -> dict:
    return state


def route_after_validate(state: dict) -> str:
    content = state["text"].removeprefix(PREPARED_PREFIX)
    return "ok" if content.strip() else "invalid"


def transform(state: dict) -> dict:
    upper = state["text"].upper()
    reversed_words = " ".join(reversed(upper.split()))
    return {"text": reversed_words}


def format_text(state: dict) -> dict:
    return {"text": f"[{state['text']}]"}


def reject(state: dict) -> dict:
    return {"text": "[rejected: empty input]"}
