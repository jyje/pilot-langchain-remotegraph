from __future__ import annotations

import typer
from langgraph_sdk import get_sync_client

from remotegraph.backends import get_backend
from remotegraph.settings import get_active_backend

app = typer.Typer(help="Deploy and interact with the example agents.")

BackendOption = typer.Option(
    None, "--backend", "-b", help="Backend name (defaults to the active backend)."
)

# The supervisor is not served by a backend; it runs locally and calls these
# three via RemoteGraph. Paths are repo-relative and assumed identical inside
# every backend's container/process working directory.
SERVED_AGENTS = {
    "researcher": "agents/researcher/graph.py:graph",
    "coder": "agents/coder/graph.py:graph",
    "reviewer": "agents/reviewer/graph.py:graph",
    "subgraph_demo": "agents/subgraph_demo/graph.py:graph",
}


def _resolve(backend: str | None) -> str:
    return backend or get_active_backend()


@app.command("deploy")
def deploy(
    backend: str | None = typer.Argument(
        None, help="Backend name (defaults to the active backend)."
    ),
) -> None:
    """Register the example agents with a backend and (re)start its stack."""
    name = _resolve(backend)
    b = get_backend(name)
    b.deploy(SERVED_AGENTS)
    b.up()
    typer.echo(f"Deployed {list(SERVED_AGENTS)} to {name} ({b.base_url})")


@app.command("list")
def list_agents(backend: str | None = BackendOption) -> None:
    """List assistants currently registered on a running backend."""
    name = _resolve(backend)
    b = get_backend(name)
    client = get_sync_client(url=b.base_url)
    for assistant in client.assistants.search():
        typer.echo(f"{assistant['assistant_id']}  graph_id={assistant.get('graph_id')}")


@app.command("call")
def call(
    name: str = typer.Argument(..., help="Agent name, e.g. researcher"),
    message: str = typer.Argument(..., help="User message to send"),
    backend: str | None = BackendOption,
) -> None:
    """Send a single message to a deployed agent and print the reply (RemoteGraph smoke test)."""
    backend_name = _resolve(backend)
    b = get_backend(backend_name)
    client = get_sync_client(url=b.base_url)
    for chunk in client.runs.stream(
        None,
        name,
        input={"messages": [{"role": "user", "content": message}]},
        stream_mode="values",
    ):
        if chunk.event == "values" and chunk.data.get("messages"):
            typer.echo(chunk.data["messages"][-1]["content"])
