"""Runs the demo scenario matrix against a live langgraph-platform backend
through RemoteGraph, and dumps raw transcripts to docs/experiments/raw/<lang>.json.

Not a pytest suite -- this is a one-off script to *produce* the evidence that
docs/experiments-ko.md / docs/experiments-en.md quote from. Run with the
langgraph-platform backend already up and the agents deployed:

    uv run remotegraph host up langgraph-platform
    uv run remotegraph agent deploy langgraph-platform
    uv run python scripts/run_experiments.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from langgraph.pregel.remote import RemoteGraph
from langgraph_sdk import get_sync_client

BASE_URL = os.environ.get("REMOTEGRAPH_BASE_URL", "http://127.0.0.1:2024")
OUT_DIR = REPO_ROOT / "docs" / "experiments" / "raw"


def remote(name: str) -> RemoteGraph:
    return RemoteGraph(name, url=BASE_URL)


def scenario_simple_qa(lang: str) -> dict:
    message = "12 곱하기 8은 얼마야? 숫자로만 답해줘." if lang == "ko" else "What is 12 times 8? Answer with just the number."
    result = remote("coder").invoke({"messages": [{"role": "user", "content": message}]})
    return {"input": message, "reply": result["messages"][-1]["content"]}


def scenario_thread_state(lang: str) -> dict:
    client = get_sync_client(url=BASE_URL)
    thread = client.threads.create()
    thread_id = thread["thread_id"]
    g = remote("coder")
    config = {"configurable": {"thread_id": thread_id}}

    if lang == "ko":
        turn1 = "내가 좋아하는 숫자는 7이야. 기억해줘."
        turn2 = "내가 좋아하는 숫자에 10을 더하면 얼마야?"
    else:
        turn1 = "My favorite number is 7. Remember it."
        turn2 = "What is my favorite number plus 10?"

    r1 = g.invoke({"messages": [{"role": "user", "content": turn1}]}, config=config)
    r2 = g.invoke({"messages": [{"role": "user", "content": turn2}]}, config=config)
    return {
        "thread_id": thread_id,
        "turn1_input": turn1,
        "turn1_reply": r1["messages"][-1]["content"],
        "turn2_input": turn2,
        "turn2_reply": r2["messages"][-1]["content"],
    }


def scenario_streaming(lang: str) -> dict:
    message = "1부터 5까지 세어줘." if lang == "ko" else "Count from 1 to 5."
    client = get_sync_client(url=BASE_URL)
    events = []
    for chunk in client.runs.stream(
        None,
        "coder",
        input={"messages": [{"role": "user", "content": message}]},
        stream_mode="values",
    ):
        if chunk.event == "values" and chunk.data.get("messages"):
            events.append(
                {"event": chunk.event, "last_message": chunk.data["messages"][-1]["content"]}
            )
        else:
            events.append({"event": chunk.event})
    return {"input": message, "event_count": len(events), "events": events}


def scenario_subgraph_branch(lang: str, *, take_reject_branch: bool) -> dict:
    text = "" if take_reject_branch else ("안녕 리모트그래프" if lang == "ko" else "hello remotegraph")
    client = get_sync_client(url=BASE_URL)
    namespaced_events = []
    for chunk in client.runs.stream(
        None,
        "subgraph_demo",
        input={"text": text},
        stream_mode="updates",
        stream_subgraphs=True,
    ):
        namespaced_events.append({"namespace": getattr(chunk, "event", None) or chunk[0] if isinstance(chunk, tuple) else None})

    result = remote("subgraph_demo").invoke({"text": text})
    return {
        "input_text": text,
        "branch": "reject" if take_reject_branch else "transform/format_text",
        "final_text": result["text"],
    }


def scenario_error_edge_case(lang: str) -> dict:
    try:
        remote("does-not-exist").invoke({"messages": [{"role": "user", "content": "ping"}]})
        return {"raised": False}
    except Exception as exc:  # noqa: BLE001 -- we want to record whatever the SDK raises
        return {"raised": True, "error_type": type(exc).__name__, "error_message": str(exc)[:500]}


def scenario_supervisor_pipeline(lang: str) -> dict:
    from agents.supervisor.graph import graph as supervisor_graph

    task = (
        "숫자를 입력받아 그 숫자의 제곱을 반환하는 한 줄짜리 파이썬 함수를 작성해줘."
        if lang == "ko"
        else "Write a one-line python function that returns the square of a number."
    )
    result = supervisor_graph.invoke({"task": task})
    return {
        "task": task,
        "research": result.get("research", "")[:800],
        "code": result.get("code", "")[:800],
        "review": result.get("review", "")[:800],
    }


def run_for_lang(lang: str) -> dict:
    print(f"=== running {lang} scenarios ===", file=sys.stderr)
    data = {}

    print("- simple_qa", file=sys.stderr)
    data["simple_qa"] = scenario_simple_qa(lang)

    print("- thread_state", file=sys.stderr)
    data["thread_state"] = scenario_thread_state(lang)

    print("- streaming", file=sys.stderr)
    data["streaming"] = scenario_streaming(lang)

    print("- subgraph_branch_transform", file=sys.stderr)
    data["subgraph_branch_transform"] = scenario_subgraph_branch(lang, take_reject_branch=False)

    print("- subgraph_branch_reject", file=sys.stderr)
    data["subgraph_branch_reject"] = scenario_subgraph_branch(lang, take_reject_branch=True)

    print("- error_edge_case", file=sys.stderr)
    data["error_edge_case"] = scenario_error_edge_case(lang)

    print("- supervisor_pipeline", file=sys.stderr)
    data["supervisor_pipeline"] = scenario_supervisor_pipeline(lang)

    return data


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for lang in ("ko", "en"):
        result = run_for_lang(lang)
        out_path = OUT_DIR / f"{lang}.json"
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
