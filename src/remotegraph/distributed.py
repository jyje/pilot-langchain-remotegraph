"""Distributed deployment: one isolated backend stack per agent.

The default `remotegraph agent deploy` registers all three agents with a
single backend on one URL. This module instead brings up **one Aegra stack
per agent**, each in its own docker compose project on its own port, each
serving exactly one graph -- so the supervisor federates three genuinely
separate servers over `RESEARCHER_URL`/`CODER_URL`/`REVIEWER_URL`, exactly as
it would across three real hosts.

It reuses the mature Aegra image (FastAPI + Postgres + Redis) via the
parameterized ``docker/aegra/docker-compose.distributed.yml`` -- each agent
gets its own Postgres/Redis (internal-only, no published host ports) so the
stacks stay isolated. Only the per-agent config file (a single-graph
``aegra.<agent>.json``) and the published HTTP port differ.

The string/port/command builders here are pure functions so they can be unit
tested without Docker; :func:`deploy` / :func:`down` shell out to compose.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from remotegraph.backends.base import REPO_ROOT

#: Agents served distributed, in the supervisor's research -> code -> review order.
DISTRIBUTED_AGENTS: dict[str, str] = {
    "researcher": "agents/researcher/graph.py:graph",
    "coder": "agents/coder/graph.py:graph",
    "reviewer": "agents/reviewer/graph.py:graph",
}

#: First agent listens here; each subsequent agent gets the next port.
DEFAULT_BASE_PORT = 2027

COMPOSE_FILE = REPO_ROOT / "docker" / "aegra" / "docker-compose.distributed.yml"
CONFIG_DIR = REPO_ROOT / "docker" / "aegra"


def agent_port(name: str, base_port: int = DEFAULT_BASE_PORT) -> int:
    """Deterministic per-agent port: base_port + the agent's index."""
    return base_port + list(DISTRIBUTED_AGENTS).index(name)


def project_name(name: str) -> str:
    """Docker compose project name isolating one agent's stack from the others."""
    return f"remotegraph-{name}"


def config_path(name: str) -> Path:
    return CONFIG_DIR / f"aegra.{name}.json"


def write_agent_config(name: str, graph_ref: str) -> Path:
    """Write a single-graph Aegra config for one agent and return its path."""
    path = config_path(name)
    config = {"dependencies": ["."], "graphs": {name: graph_ref}}
    path.write_text(json.dumps(config, indent=2) + "\n")
    return path


def compose_command(name: str, port: int, *action: str) -> list[str]:
    """Build the `docker compose` argv for one agent's stack."""
    return [
        "docker",
        "compose",
        "-p",
        project_name(name),
        "-f",
        str(COMPOSE_FILE),
        *action,
    ]


def compose_env(name: str, port: int) -> dict[str, str]:
    """Env vars substituted into docker-compose.distributed.yml for one agent."""
    return {
        "AEGRA_PORT": str(port),
        "AGENT_CONFIG": str(config_path(name)),
        "AGENT_NAME": name,
    }


def agent_url(name: str, base_port: int = DEFAULT_BASE_PORT, host: str = "127.0.0.1") -> str:
    return f"http://{host}:{agent_port(name, base_port)}"


def urls(base_port: int = DEFAULT_BASE_PORT) -> dict[str, str]:
    """Map each agent to the `*_URL` value the supervisor reads."""
    return {f"{name.upper()}_URL": agent_url(name, base_port) for name in DISTRIBUTED_AGENTS}


def _run(name: str, port: int, *action: str) -> None:
    import os

    env = {**os.environ, **compose_env(name, port)}
    subprocess.run(compose_command(name, port, *action), cwd=REPO_ROOT, env=env, check=True)


def deploy(base_port: int = DEFAULT_BASE_PORT) -> dict[str, str]:
    """Bring up one Aegra stack per agent. Returns the supervisor `*_URL` map."""
    for name, graph_ref in DISTRIBUTED_AGENTS.items():
        write_agent_config(name, graph_ref)
        _run(name, agent_port(name, base_port), "up", "-d", "--build")
    return urls(base_port)


def down(base_port: int = DEFAULT_BASE_PORT) -> None:
    """Tear down every per-agent stack (and its volumes)."""
    for name in DISTRIBUTED_AGENTS:
        _run(name, agent_port(name, base_port), "down", "-v")
