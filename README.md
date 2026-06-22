<div align="center">

# jyje/pilot-langchain-remotegraph

Pilot: drive LangGraph's `RemoteGraph` against three self-hosted, LangGraph-Platform-API-compatible backends — through one `remotegraph` CLI.

[English](README.md) / [한국어](README-ko.md)

</div>

## Agent Protocol

The reason `RemoteGraph` works the same way against three different servers isn't a coincidence -- all three implement [**Agent Protocol**](https://github.com/langchain-ai/agent-protocol), LangChain's framework-agnostic spec for serving LLM agents in production (runs, threads, long-term memory store, streaming, agent introspection). **Checking whether independent Agent Protocol implementations actually interoperate with the official client is this pilot's central goal**, not an incidental implementation detail.

| Backend | Agent Protocol relationship | Source |
|---|---|---|
| LangGraph Platform self-hosted (`langgraph dev`) | Reference implementation -- "LangGraph Platform implements a superset of this protocol" | [langchain-ai/agent-protocol](https://github.com/langchain-ai/agent-protocol) README |
| [`aegra`](https://github.com/aegra/aegra) | Community implementation, built explicitly to the Agent Protocol spec | [aegra docs](https://docs.aegra.dev/) |
| [`open-langgraph-platform`](https://github.com/HyunjunJeon/open-langgraph-platform) | Community implementation -- "Agent Protocol server built on LangGraph" | project README |

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

### Distributed deployment (each agent on its own server)

This pilot deploys all three agents to one backend for convenience, but `agents/supervisor/graph.py` resolves each agent's URL independently — set `RESEARCHER_URL`/`CODER_URL`/`REVIEWER_URL` instead of the shared `REMOTEGRAPH_BASE_URL` to point the supervisor at three separately hosted servers (e.g. one Aegra instance per agent, each on its own host):

```bash
export RESEARCHER_URL=http://research-agent.internal:8000
export CODER_URL=http://coder-agent.internal:8000
export REVIEWER_URL=http://reviewer-agent.internal:8000
```

A per-agent env var always wins over `REMOTEGRAPH_BASE_URL`, which stays as a fallback for the single-backend case above.

### Subgraph control, verified

`researcher`/`coder`/`reviewer` are flat ReAct agents, so they can't prove `RemoteGraph` actually controls *inside* a remote graph rather than just calling it as an opaque unit. [`agents/subgraph_demo/`](agents/subgraph_demo/) is a small, deterministic, LLM-free graph with a real subgraph node -- `prepare -> inner (subgraph: validate -> {transform -> format_text | reject}) -> finalize`, with branching -- used to check this for real against a live backend in [`notebooks/subgraph_verification.ipynb`](notebooks/subgraph_verification.ipynb). Confirmed:

- `stream_subgraphs=True` surfaces the subgraph's own internal node updates as separately namespaced events (`updates|inner:<ns-id>`) -- including *which branch* (`transform`/`format_text` vs `reject`) was actually taken -- not just `inner`'s aggregate result.
- `interrupt_before=["inner"]` actually pauses the run *before* the subgraph executes (`state.next == ("inner",)`, with `state.values` still untouched by it), and resuming continues correctly through the subgraph to completion.
- Both hold through the actual `RemoteGraph` class that `agents/supervisor/graph.py` uses, not just the raw `langgraph_sdk` client.

### Workflow / subgraph-workflow patterns, defined in YAML

[`src/remotegraph/workflow.py`](src/remotegraph/workflow.py) loads a graph's topology from YAML (or JSON -- PyYAML parses it unchanged) instead of imperative `.add_node()`/`.add_edge()` calls:

- a node's `fn:` is a dotted `"package.module:attr"` import path (a plain function node);
- a node's `workflow:` points at another workflow file, loaded recursively and added as a compiled **subgraph** node -- the same composition `agents/subgraph_demo` uses;
- edges are `[from, to]` pairs (`__start__`/`__end__` sentinels included), or a `conditional:` block (`source`, routing `fn:`, `targets:` map) compiled via `add_conditional_edges`.

`agents/subgraph_demo/workflow.yaml` + `inner_workflow.yaml` are the canonical "subgraph workflow pattern" example -- `agents/subgraph_demo/graph.py` is just `graph = load_workflow(...)`. [`agents/workflows/research_pipeline.yaml`](agents/workflows/research_pipeline.yaml) is a "plain workflow pattern" example: it re-declares `agents/supervisor/graph.py`'s `research -> code -> review` topology by referencing that file's *existing* node functions, and `tests/test_workflow.py` asserts the two produce structurally identical graphs -- proving the pattern without touching the already-tested hand-written supervisor.

### Autonomous supervisor (deepagents), evaluated

Asked to evaluate whether an autonomous, LLM-routed supervisor based on [`deepagents`](https://github.com/langchain-ai/deepagents) gets the same subgraph-level control verified above -- it does not, and that's a real distinction, not a bug:

- `deepagents.create_deep_agent` delegates to sub-agents via a `task` *tool* -- an LLM decision at runtime, not LangGraph's structural subgraph composition. From `RemoteGraph`'s perspective, that delegation is just an ordinary tool-call/tool-result message, not a separately namespaced subgraph stream event. **`stream_subgraphs`/`interrupt_before` do not apply to it.**
- It does get something else useful: `deepagents.middleware.subagents.CompiledSubAgent.runnable` accepts anything satisfying `Runnable`, and `RemoteGraph` is one. [`agents/autonomous_supervisor/graph.py`](agents/autonomous_supervisor/graph.py) registers `researcher`/`coder`/`reviewer` directly as `CompiledSubAgent`s -- **no wrapper tool/function code** -- and the deep agent's `task` tool genuinely dispatches to the real remote servers. Verified end-to-end in [`notebooks/autonomous_supervisor.ipynb`](notebooks/autonomous_supervisor.ipynb): given one task, it autonomously called `coder` (twice, refining its own request) then `reviewer`, and returned the combined result.

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
- `api/quotas.py` used `from __future__ import annotations` together with `User` imported only under `TYPE_CHECKING` and a bare string `"Request"` annotation with no import at all -- both fine for static type checkers, but FastAPI/Pydantic need to resolve these forward refs at runtime to build the OpenAPI schema, so `GET /openapi.json` (and therefore `/docs`) 500'd on every request. Fixed by importing both at module level.

Separately (not patched, just routed around): `POST /assistants/search` filters by the caller's identity, but the server's own auto-seeded default assistants are owned by `user_id="system"` — so `remotegraph agent list --backend open-langgraph` returns an empty list even though the agents work fine. `remotegraph agent call`/`RemoteGraph` pass a graph ID directly and are unaffected.

## Experiment results

[`REPORT.md`](REPORT.md) has real captured logs and screenshots from running all three backends end-to-end, plus reproducible Jupyter notebooks per backend under [`notebooks/`](notebooks/).

For a prompt-by-prompt demonstration across multiple scenarios (simple call, multi-turn thread state, streaming, subgraph branch control, error handling, multi-agent pipeline) with real captured replies, see [`docs/experiments-en.md`](docs/experiments-en.md) (English) / [`docs/experiments-ko.md`](docs/experiments-ko.md) (한국어), reproducible via [`scripts/run_experiments.py`](scripts/run_experiments.py).

## Project layout

```
src/remotegraph/      # the CLI (typer): cli.py, config.py, host.py, agent.py, backends/, workflow.py (YAML loader)
agents/                # researcher/coder/reviewer (served) + supervisor (RemoteGraph caller)
agents/subgraph_demo/  # subgraph workflow pattern example, defined via workflow.yaml + inner_workflow.yaml
agents/autonomous_supervisor/ # deepagents-based supervisor (CompiledSubAgent(runnable=RemoteGraph(...)))
agents/workflows/      # plain workflow pattern YAML examples
docker/aegra/          # Dockerfile + docker-compose.yml + aegra.json
docker/open-langgraph/ # Dockerfile + docker-compose.yml + open_langgraph.json
vendor/                # git submodule: jyje/open-langgraph-platform fork
langgraph.json         # config consumed by the langgraph-platform (dev) backend
```
