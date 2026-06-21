# Experiment Report: RemoteGraph across three self-hosted backends

This report captures the results of actually running all three backends end-to-end via `remotegraph`, with real LLM calls against a local [LM Studio](https://lmstudio.ai/) server (`google/gemma-4-e4b`) under [OrbStack](https://orbstack.dev/). Full, reproducible, re-executable experiments live in [`notebooks/`](notebooks/) — this document is the human-readable summary of one execution of each.

## Summary

| Backend | Notebook | Status | Swagger / API docs |
|---|---|---|---|
| `aegra` | [`aegra.ipynb`](notebooks/aegra.ipynb) | ✅ deploy → list → call ×3 → supervisor pipeline → teardown, all clean | ![aegra Swagger UI](notebooks/screenshots/aegra-swagger.png) |
| `open-langgraph-platform` | [`open_langgraph_platform.ipynb`](notebooks/open_langgraph_platform.ipynb) | ✅ same, after the upstream fixes in [Known upstream issues](README.md#known-upstream-issues) | ![open-langgraph-platform Swagger UI](notebooks/screenshots/open-langgraph-swagger.png) |
| `langgraph-platform` (`langgraph dev`) | [`langgraph_platform.ipynb`](notebooks/langgraph_platform.ipynb) | ✅ same, no Docker | ![LangGraph Platform API docs](notebooks/screenshots/langgraph-platform-docs.png) |
| Subgraph control | [`subgraph_verification.ipynb`](notebooks/subgraph_verification.ipynb) | ✅ `stream_subgraphs` + `interrupt_before` confirmed working against a real subgraph node, via `langgraph-platform` | — |

Every backend was exercised through the identical sequence: `backend.deploy(...)` → `backend.up()` → list assistants → call `coder`/`researcher`/`reviewer` directly → run the `supervisor` graph locally (which calls all three over `RemoteGraph`) → `backend.down()`.

## aegra

```
$ remotegraph host up aegra
aegra is up at http://127.0.0.1:2026

$ remotegraph agent list --backend aegra
ad9aa870-1e45-562b-a83d-73b96694ea13  graph_id=coder
c926ac5a-b04e-5949-878a-8e4830d4338b  graph_id=researcher
ca7018db-539a-5a5f-b9c2-8622330bec7d  graph_id=reviewer

$ remotegraph agent call coder "What is 13 * 7? Just the number." --backend aegra
91

$ remotegraph agent call researcher "What is LangGraph in one sentence?" --backend aegra
LangGraph is a library built by the LangChain team that allows developers to create
complex, stateful AI applications—including single or multi-agent systems—by modeling
the interaction flow as a deterministic graph.

$ remotegraph agent call reviewer "Review this code: def add(a, b): return a + b" --backend aegra
The code is correct and achieves its intended purpose of adding two numbers.
Verdict: Passes linting.
```

Supervisor pipeline (research → code → review), driven entirely over `RemoteGraph`:

```
--- research ---
square = lambda x: x * x          # (alternatively: pow(x, 2))

--- code ---
square = lambda x: x * x

--- review ---
The code is correct and follows good Python style for a simple anonymous
function assignment. Verdict: Correct and idiomatic.
```

## open-langgraph-platform

Same sequence, against the Docker image built from the vendored fork (`vendor/open-langgraph-platform`, branch `fix/immutable-index-now-predicate`):

```
$ remotegraph host up open-langgraph
open-langgraph is up at http://127.0.0.1:8001

$ remotegraph agent call coder "What is 13 * 7? Just the number." --backend open-langgraph
91

$ remotegraph agent call researcher "What is LangGraph in one sentence?" --backend open-langgraph
LangGraph is an open-source framework within the LangChain ecosystem that allows
developers to build, manage, and execute complex AI agent workflows as controllable,
stateful graphs.

$ remotegraph agent call reviewer "Review this code: def add(a, b): return a + b" --backend open-langgraph
The code is correct and follows Python style conventions. Verdict: Passes review.
```

Supervisor pipeline:

```
--- research ---
def square(n): return n * n      # (alternatively: n ** 2)

--- code ---
square = lambda n: n * n

--- review ---
Verdict: Correct. Syntactically correct, executes as expected, and uses a
concise, idiomatic Python lambda function to map the squaring operation.
```

`remotegraph agent list --backend open-langgraph` returns an empty list (a real upstream multi-tenancy filtering bug — see [README.md](README.md#known-upstream-issues)); `agent call`/`RemoteGraph` are unaffected since they address a graph ID directly, as shown above.

## langgraph-platform (`langgraph dev`)

No Docker — `backend.up()` spawns `langgraph dev` as a local subprocess:

```
$ remotegraph agent deploy langgraph-platform
Deployed ['researcher', 'coder', 'reviewer'] to langgraph-platform (http://127.0.0.1:2024)

$ remotegraph agent list --backend langgraph-platform
ca7018db-539a-5a5f-b9c2-8622330bec7d  graph_id=reviewer
c926ac5a-b04e-5949-878a-8e4830d4338b  graph_id=researcher
ad9aa870-1e45-562b-a83d-73b96694ea13  graph_id=coder

$ remotegraph agent call coder "What is 16 + 26? Just the number." --backend langgraph-platform
42
```

Supervisor pipeline:

```
--- research ---
square = lambda x: x**2

--- code ---
square = lambda x: x**2

--- review ---
Verdict: Mostly Correct, but Stylistically Flawed
The code is functionally correct... using a simple assignment for a multi-line
or complex function body is usually better served by `def`.
```

Notably, this run's `reviewer` gave a stricter, more stylistically opinionated verdict than the other two backends for the same lambda-based code — a reminder that these are real (small, local) LLM calls, not fixtures, and minor wording/judgment varies run to run.

## Subgraph control

`researcher`/`coder`/`reviewer` are flat ReAct agents and can't prove `RemoteGraph` controls *inside* a remote graph rather than calling it as an opaque unit. [`agents/subgraph_demo/graph.py`](agents/subgraph_demo/graph.py) is a small, deterministic, LLM-free graph (`prepare -> inner (subgraph) -> finalize`) built specifically to check this — see [`notebooks/subgraph_verification.ipynb`](notebooks/subgraph_verification.ipynb) for the full run against `langgraph-platform`.

```
=== stream_subgraphs=True ===
updates -> {'prepare': {'text': '[prepared] hello'}}
updates|inner:1e8055ec-dce0-2da1-0f28-acc26500cfee -> {'shout': {'text': '[PREPARED] HELLO'}}
updates -> {'inner': {'text': '[PREPARED] HELLO'}}
updates -> {'finalize': {'text': '[PREPARED] HELLO [finalized]'}}

=== interrupt_before=["inner"] ===
updates -> {'prepare': {'text': '[prepared] world'}}
updates -> {'__interrupt__': []}
next: ['inner']
values: {'text': '[prepared] world'}      # subgraph hasn't run yet

=== resume ===
updates -> {'inner': {'text': '[PREPARED] WORLD'}}
updates -> {'finalize': {'text': '[PREPARED] WORLD [finalized]'}}
next: []
values: {'text': '[PREPARED] WORLD [finalized]'}

=== same thing through the actual RemoteGraph class ===
paused result: {'text': '[prepared] via RemoteGraph'}
next: ('inner',)
final: {'text': '[PREPARED] VIA REMOTEGRAPH [finalized]'}
```

Confirmed: subgraph-internal events are visible with a distinct namespace (`updates|inner:<ns-id>`), `interrupt_before` genuinely pauses before the subgraph executes (not just before some equivalent top-level checkpoint), and resuming continues through it correctly — through `RemoteGraph` itself, not just the raw SDK client.

## Reproducing this

```bash
uv sync
cp .env.sample .env   # configure your OpenAI-compatible endpoint
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/aegra.ipynb
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/open_langgraph_platform.ipynb
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/langgraph_platform.ipynb
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/subgraph_verification.ipynb
```

Each notebook is self-contained: it starts its backend, deploys the agents, runs the calls and the supervisor pipeline, and tears the backend back down at the end.
