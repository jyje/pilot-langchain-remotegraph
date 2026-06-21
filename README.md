<div align="center">

# jyje/pilot-langchain-remotegraph

Pilot: drive LangGraph's `RemoteGraph` against three self-hosted, LangGraph-Platform-API-compatible backends — through one `remotegraph` CLI.

[English](README.md) / [한국어](README-ko.md)

</div>

## Overview

This repo is a pilot that answers one question: **does `langgraph.pregel.remote.RemoteGraph` work the same way against any server that implements the LangGraph Platform REST API (`/assistants`, `/threads`, `/runs`), not just LangGraph Platform Cloud?**

Four example agents demonstrate the pattern:

| Agent | Role |
|---|---|
| `researcher` | Web search (DuckDuckGo) |
| `coder` | Writes and executes Python (`run_python` tool) |
| `reviewer` | Lints code with `ruff` (`lint_python` tool) |
| `supervisor` | Runs locally, calls the three above **via `RemoteGraph`** in a research → code → review pipeline |

`researcher`/`coder`/`reviewer` get deployed to a backend; `supervisor` never is — it only ever talks to them over the network, exactly as it would to a real LangGraph Platform deployment.

## Backends

| Backend | How it runs | Port | Notes |
|---|---|---|---|
| [`aegra`](https://github.com/aegra/aegra) | Docker (FastAPI + Postgres + Redis) | `2026` | Most mature of the OSS alternatives |
| [`open-langgraph-platform`](https://github.com/HyunjunJeon/open-langgraph-platform) | Docker (FastAPI + Postgres + Redis), vendored as a git submodule from [jyje's fork](https://github.com/jyje/open-langgraph-platform) with local bug fixes — see [Known upstream issues](#known-upstream-issues) | `8001` | Pre-1.0, single-maintainer |
| LangGraph Platform self-hosted | `langgraph dev` (in-memory subprocess, **not** Docker) | `2024` | The real Docker path (`langgraph up`) needs an Enterprise license key, so this pilot uses the free `langgraph dev` server instead — it exposes the identical REST API |

## Requirements

- Python 3.14 ([`uv`](https://docs.astral.sh/uv/) manages the interpreter and venv)
- Docker (this pilot was tested against [OrbStack](https://orbstack.dev/))
- An OpenAI-compatible LLM endpoint. Defaults to a local [LM Studio](https://lmstudio.ai/) server.

## Quickstart

```bash
uv sync
cp .env.sample .env   # adjust OPENAI_BASE_URL / OPENAI_MODEL / OPENAI_API_KEY
uv run remotegraph --help
```

Bring up a backend, deploy the three agents to it, and call one:

```bash
uv run remotegraph host up aegra
uv run remotegraph agent deploy aegra
uv run remotegraph agent call coder "What is 12 * 8?" --backend aegra
uv run remotegraph host down aegra
```

Run the full research → code → review pipeline through the supervisor (point it at whichever backend is currently up):

```bash
REMOTEGRAPH_BASE_URL=http://127.0.0.1:2026 uv run python -c "
from agents.supervisor.graph import graph
result = graph.invoke({'task': 'Write a one-line python function that returns the square of a number.'})
print(result['review'])
"
```

Swap `aegra` for `open-langgraph` (port `8001`) or `langgraph-platform` (port `2024`, no Docker — `up` just spawns `langgraph dev`) to test the other backends.

## CLI reference

```
remotegraph config show|init|set <key> <value>   # remotegraph.toml (active_backend, ...)
remotegraph host list|up|down|status|logs [backend]
remotegraph agent deploy|list [backend]
remotegraph agent call <name> "<message>" [--backend <backend>]
```

`backend` is one of `aegra`, `open-langgraph`, `langgraph-platform`; omit it to use the configured `active_backend` (`remotegraph config set active_backend <name>`).

## Development

```bash
uv run ruff format . && uv run ruff check .
uv run ty check
uv run pytest tests/             # smoke tests against live backends auto-skip if unreachable
```

## Known upstream issues

`open-langgraph-platform` is pre-1.0; getting it running surfaced real bugs, fixed on a branch of [jyje's fork](https://github.com/jyje/open-langgraph-platform/tree/fix/immutable-index-now-predicate) (vendored as the `vendor/open-langgraph-platform` submodule):

- Three Alembic migrations created a partial index with `WHERE ... > NOW()` — Postgres rejects non-`IMMUTABLE` functions in index predicates, so `alembic upgrade head` crash-looped on a fresh database.
- `AUTH_TYPE=noop` returned `is_authenticated=False`, but `get_current_user` rejects any non-authenticated request — so noop mode never actually permitted access, contradicting its own docstring.
- `pyproject.toml` only sets a lower bound on `a2a-sdk` (`>=0.3.22`); a plain `pip install .` resolves a newer major version with breaking API changes. This repo's `docker/open-langgraph/Dockerfile` pins it to the version in their lockfile.

Separately (not patched, just routed around): `POST /assistants/search` filters by the caller's identity, but the server's own auto-seeded default assistants are owned by `user_id="system"` — so `remotegraph agent list --backend open-langgraph` returns an empty list even though the agents work fine. `remotegraph agent call`/`RemoteGraph` pass a graph ID directly and are unaffected.

## Project layout

```
src/remotegraph/      # the CLI (typer): cli.py, config.py, host.py, agent.py, backends/
agents/                # researcher/coder/reviewer (served) + supervisor (RemoteGraph caller)
docker/aegra/          # Dockerfile + docker-compose.yml + aegra.json
docker/open-langgraph/ # Dockerfile + docker-compose.yml + open_langgraph.json
vendor/                # git submodule: jyje/open-langgraph-platform fork
langgraph.json         # config consumed by the langgraph-platform (dev) backend
```
