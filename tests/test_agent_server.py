"""Tests for the standalone FastAPI agent server.

The streaming/SSE helpers are pure and tested directly with a fake graph. The
HTTP layer is exercised via FastAPI's TestClient, which is skipped if FastAPI
can't be imported (e.g. on a Python build whose pydantic is incompatible).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from remotegraph import agent_server


class FakeGraph:
    """Minimal `graph.stream(...)` stand-in: replays preset events per mode."""

    def __init__(self, values: list[dict] | None = None) -> None:
        self._values = values or [
            {"messages": [{"role": "user", "content": "hi"}]},
            {"messages": [{"role": "assistant", "content": "the answer is 96"}]},
        ]

    def stream(self, input, config=None, *, stream_mode, subgraphs=False, **kwargs):
        modes = stream_mode if isinstance(stream_mode, list) else [stream_mode]
        for state in self._values:
            if subgraphs:
                yield ((), modes[0], state) if len(modes) > 1 else ((), state)
            elif len(modes) > 1:
                yield (modes[0], state)
            else:
                yield state


def _parse_sse(body: str) -> list[tuple[str, Any]]:
    events: list[tuple[str, Any]] = []
    for block in body.strip().split("\n\n"):
        event = data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[len("event: ") :]
            elif line.startswith("data: "):
                data = line[len("data: ") :]
        if event is not None:
            events.append((event, json.loads(data) if data is not None else None))
    return events


def test_sse_format_matches_spec() -> None:
    raw = agent_server._sse("values", {"a": 1}).decode()
    assert raw == 'event: values\ndata: {"a": 1}\n\n'


def test_stream_events_values_mode_emits_final_state() -> None:
    chunks = b"".join(agent_server._stream_events(FakeGraph(), {"input": {"x": 1}}))
    events = _parse_sse(chunks.decode())

    assert [e for e, _ in events] == ["values", "values", "end"]
    # RemoteGraph.invoke keeps the last `values` payload as the result.
    last_values = [d for e, d in events if e == "values"][-1]
    assert last_values["messages"][-1]["content"] == "the answer is 96"


def test_stream_events_subgraph_namespacing() -> None:
    body = {"input": {"x": 1}, "stream_mode": ["updates"], "stream_subgraphs": True}
    events = _parse_sse(b"".join(agent_server._stream_events(FakeGraph(), body)).decode())
    # Root-namespace events carry no `|ns` suffix.
    assert events[0][0] == "updates"


def test_stream_events_surfaces_errors_as_error_event() -> None:
    class Boom:
        def stream(self, *a, **k):
            raise RuntimeError("kaboom")
            yield  # pragma: no cover -- makes this a generator

    events = _parse_sse(b"".join(agent_server._stream_events(Boom(), {"input": {}})).decode())
    assert events[0][0] == "error"
    assert events[0][1]["message"] == "kaboom"


def test_load_graph_rejects_reference_without_attr() -> None:
    with pytest.raises(ValueError, match="module:attr"):
        agent_server.load_graph("agents/researcher/graph.py")


# --- HTTP layer (needs FastAPI) -------------------------------------------------

try:
    from fastapi.testclient import TestClient

    _FASTAPI_OK = True
except Exception:  # noqa: BLE001 -- pydantic/python build mismatch, etc.
    _FASTAPI_OK = False

fastapi_only = pytest.mark.skipif(not _FASTAPI_OK, reason="FastAPI unavailable in this runtime")


@fastapi_only
def test_health_endpoint() -> None:
    client = TestClient(agent_server.create_app(FakeGraph(), assistant_id="coder"))
    resp = client.get("/ok")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "assistant_id": "coder"}


@fastapi_only
def test_assistant_graph_404s_on_mismatched_id() -> None:
    client = TestClient(agent_server.create_app(FakeGraph(), assistant_id="coder"))
    assert client.get("/assistants/coder/graph").status_code == 200
    assert client.get("/assistants/researcher/graph").status_code == 404


@fastapi_only
def test_runs_stream_returns_event_stream() -> None:
    client = TestClient(agent_server.create_app(FakeGraph()))
    resp = client.post("/runs/stream", json={"input": {"messages": []}})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    events = _parse_sse(resp.text)
    last_values = [d for e, d in events if e == "values"][-1]
    assert last_values["messages"][-1]["content"] == "the answer is 96"
