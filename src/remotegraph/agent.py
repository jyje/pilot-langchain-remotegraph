from __future__ import annotations

import subprocess

import typer
from langgraph_sdk import get_sync_client

from remotegraph import distributed
from remotegraph.backends import get_backend
from remotegraph.backends.base import REPO_ROOT
from remotegraph.settings import get_active_backend

app = typer.Typer(help="Deploy and interact with the example agents.")

# The three standalone FastAPI agent servers (docker/agent-server) -- the
# "agent = microservice" path, no Postgres/Redis.
SERVERS_COMPOSE = REPO_ROOT / "docker" / "agent-server" / "docker-compose.yml"

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


def _echo_exports(urls: dict[str, str]) -> None:
    """Print the shell `export *_URL=...` lines the supervisor reads."""
    typer.echo("\n# Point the supervisor at the per-agent servers:")
    for var, url in urls.items():
        typer.echo(f"export {var}={url}")


# --- A: distributed deploy -- one full Aegra stack per agent --------------------


@app.command("deploy-distributed")
def deploy_distributed(
    base_port: int = typer.Option(
        distributed.DEFAULT_BASE_PORT, help="Port for the first agent; others increment from it."
    ),
) -> None:
    """Bring up one isolated Aegra stack per agent, each on its own URL."""
    urls = distributed.deploy(base_port)
    typer.echo(f"Deployed {list(distributed.DISTRIBUTED_AGENTS)} as separate Aegra stacks")
    _echo_exports(urls)


@app.command("stop-distributed")
def stop_distributed(
    base_port: int = typer.Option(distributed.DEFAULT_BASE_PORT, help="Base port used at deploy."),
) -> None:
    """Tear down every per-agent Aegra stack started by deploy-distributed."""
    distributed.down(base_port)
    typer.echo("Stopped all per-agent Aegra stacks")


@app.command("urls")
def urls(
    base_port: int = typer.Option(distributed.DEFAULT_BASE_PORT, help="Base port of the agents."),
) -> None:
    """Print the supervisor `export *_URL=...` lines for the distributed agents."""
    _echo_exports(distributed.urls(base_port))


# --- B: standalone FastAPI agent servers ----------------------------------------


@app.command("serve")
def serve(
    name: str = typer.Argument(..., help="Agent name, e.g. researcher"),
    port: int = typer.Option(8000, help="Port to bind the FastAPI server to."),
    host: str = typer.Option("127.0.0.1", help="Host to bind to."),
) -> None:
    """Run a single agent as a standalone FastAPI server (no backend/Docker)."""
    import uvicorn

    from remotegraph.agent_server import create_app, load_graph

    graph_ref = SERVED_AGENTS.get(name, name)
    app_ = create_app(load_graph(graph_ref), assistant_id=name)
    typer.echo(f"Serving {name} at http://{host}:{port}  (graph={graph_ref})")
    uvicorn.run(app_, host=host, port=port)


@app.command("up-servers")
def up_servers() -> None:
    """Bring up the three standalone FastAPI agent servers via docker compose."""
    subprocess.run(
        ["docker", "compose", "-f", str(SERVERS_COMPOSE), "up", "-d", "--build"],
        cwd=REPO_ROOT,
        check=True,
    )
    _echo_exports(
        {
            "RESEARCHER_URL": "http://localhost:8101",
            "CODER_URL": "http://localhost:8102",
            "REVIEWER_URL": "http://localhost:8103",
        }
    )


@app.command("down-servers")
def down_servers() -> None:
    """Stop the three standalone FastAPI agent servers."""
    subprocess.run(
        ["docker", "compose", "-f", str(SERVERS_COMPOSE), "down"],
        cwd=REPO_ROOT,
        check=True,
    )
    typer.echo("Stopped the standalone agent servers")
