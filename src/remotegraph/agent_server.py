"""Standalone FastAPI server that exposes a single LangGraph agent.

This is the "agent = microservice" path: instead of registering all three
agents with one heavyweight backend (aegra/open-langgraph, each needing
Postgres + Redis), this serves exactly **one** compiled graph over the slice
of the LangGraph Platform REST API that `RemoteGraph` actually exercises for
a stateless `invoke()`/`stream()` -- `POST /runs/stream`. Any number of these
can run on their own URLs and be federated by `agents/supervisor/graph.py`
via `RESEARCHER_URL`/`CODER_URL`/`REVIEWER_URL`.

It is deliberately **stateless** (no thread persistence): each run is
independent, which is all the supervisor pipeline needs. For multi-turn
thread state / interrupts backed by a real store, use the full aegra backend
(`remotegraph agent deploy-distributed`) instead.

Run it directly:

    AGENT_GRAPH=agents/researcher/graph.py:graph PORT=8101 \
        python -m remotegraph.agent_server

`create_app(graph)` stays free of LangGraph imports -- it only calls
`graph.stream(...)` -- so it can be unit-tested against a fake graph without
pulling the full agent runtime.
"""

from __future__ import annotations

import importlib
import json
import os
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI


def load_graph(ref: str) -> Any:
    """Resolve a graph reference to a compiled graph object.

    Accepts both the LangGraph-config file form used in this repo's deploy
    configs (``"agents/researcher/graph.py:graph"``) and a plain dotted module
    form (``"agents.researcher.graph:graph"``). Importing the module pulls in
    LangGraph/LangChain, so this is only called at server startup, never by
    ``create_app``.
    """
    target, _, attr = ref.partition(":")
    if not attr:
        raise ValueError(f"Graph reference {ref!r} must be of the form 'module:attr'")
    if target.endswith(".py") or "/" in target:
        module_path = target.removesuffix(".py").replace("/", ".")
    else:
        module_path = target
    module = importlib.import_module(module_path)
    return getattr(module, attr)


def _normalize_modes(stream_mode: Any) -> list[str]:
    if stream_mode is None:
        return ["values"]
    if isinstance(stream_mode, str):
        return [stream_mode]
    return list(stream_mode)


def _sse(event: str, data: Any) -> bytes:
    """Format one Server-Sent Event the way langgraph_sdk's SSEDecoder reads it."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


def _stream_events(graph: Any, body: dict[str, Any]) -> Iterator[bytes]:
    """Run the graph and yield Platform-style SSE chunks.

    Mirrors how LangGraph Platform names streamed events so `RemoteGraph` can
    split them back into ``(mode, namespace)``: a plain ``values``/``updates``
    event for the root graph, and ``<mode>|<ns...>`` for subgraph events when
    ``stream_subgraphs`` is requested.
    """
    modes = _normalize_modes(body.get("stream_mode"))
    subgraphs = bool(body.get("stream_subgraphs"))
    config = body.get("config") or {}
    multi = len(modes) > 1

    stream_input: Any = body.get("input")
    if stream_input is None and body.get("command") is not None:
        # Resume/Command-style runs: rebuild the Command from the wire payload.
        from langgraph.types import Command

        stream_input = Command(**body["command"])

    kwargs: dict[str, Any] = {"stream_mode": modes, "subgraphs": subgraphs}
    for key in ("interrupt_before", "interrupt_after"):
        if body.get(key) is not None:
            kwargs[key] = body[key]

    try:
        for item in graph.stream(stream_input, config, **kwargs):
            ns: tuple[str, ...] = ()
            if subgraphs:
                if isinstance(item, tuple) and len(item) == 3:
                    ns, mode, data = item
                else:
                    ns, data = item  # type: ignore[misc]
                    mode = modes[0]
            elif multi:
                mode, data = item
            else:
                mode, data = modes[0], item
            event = mode if not ns else "|".join((mode, *ns))
            yield _sse(event, data)
    except Exception as exc:  # noqa: BLE001 -- surface as a Platform error event
        yield _sse("error", {"error": type(exc).__name__, "message": str(exc)})
        return

    yield _sse("end", None)


def create_app(graph: Any, *, assistant_id: str = "agent") -> FastAPI:
    """Build a FastAPI app serving a single compiled `graph`.

    Only ``graph.stream(...)`` (and, best-effort, ``graph.get_graph()``) is
    used, so any object with that surface -- including a test double -- works.
    FastAPI is imported lazily here so the streaming helpers above stay
    importable without it.
    """
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse, StreamingResponse
    from starlette.requests import Request

    app = FastAPI(title=f"remotegraph agent: {assistant_id}")

    @app.get("/ok")
    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "assistant_id": assistant_id}

    @app.get("/info")
    def info() -> dict[str, Any]:
        return {"assistant_id": assistant_id, "stateless": True}

    @app.get("/assistants/{requested_id}/graph")
    def assistant_graph(requested_id: str) -> JSONResponse:
        try:
            drawable = graph.get_graph().to_json()
        except Exception:  # noqa: BLE001 -- introspection is best-effort
            drawable = {"nodes": [], "edges": []}
        return JSONResponse(drawable)

    async def run_stream(request: Request) -> StreamingResponse:
        body = await request.json()
        return StreamingResponse(
            _stream_events(graph, body),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    # Registered as raw Starlette routes (not FastAPI path operations) so the
    # streaming body is read straight off the Request -- no pydantic request
    # model, which a deferred `Request` annotation would otherwise trip over.
    # Stateless: a threaded run is served identically to a thread-less one
    # (thread_id is accepted but not persisted).
    app.add_route("/runs/stream", run_stream, methods=["POST"])
    app.add_route("/threads/{thread_id}/runs/stream", run_stream, methods=["POST"])

    return app


def main() -> None:
    import uvicorn

    ref = os.environ.get("AGENT_GRAPH")
    if not ref:
        raise SystemExit("AGENT_GRAPH must be set, e.g. agents/researcher/graph.py:graph")
    assistant_id = os.environ.get("AGENT_ID", ref.rsplit(":", 1)[-1])
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    app = create_app(load_graph(ref), assistant_id=assistant_id)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
