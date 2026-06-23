"""Verify the standalone FastAPI agent server end-to-end through RemoteGraph.

Starts `python -m remotegraph.agent_server` serving agents/subgraph_demo (a
deterministic, LLM-free graph with a real subgraph node), then drives it with
the actual `langgraph.pregel.remote.RemoteGraph` -- the same class
agents/supervisor uses -- proving the lightweight single-graph server (no
Postgres/Redis) federates correctly, *including* RemoteGraph's subgraph
streaming control, not just plain calls.

No backend, no Docker, no LLM required:

    uv run python scripts/verify_agent_server.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PORT = int(os.environ.get("VERIFY_PORT", "8199"))
URL = f"http://127.0.0.1:{PORT}"


def _wait_for_ok(timeout_s: float = 20.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{URL}/ok", timeout=1) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(0.2)
    raise SystemExit(f"agent server did not come up at {URL}")


def main() -> None:
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(REPO_ROOT / "src"), str(REPO_ROOT)]),
        "AGENT_GRAPH": "agents/subgraph_demo/graph.py:graph",
        "AGENT_ID": "subgraph_demo",
        "PORT": str(PORT),
        "HOST": "127.0.0.1",
    }
    server = subprocess.Popen(
        [sys.executable, "-m", "remotegraph.agent_server"],
        env=env,
        cwd=REPO_ROOT,
    )
    try:
        _wait_for_ok()

        from langgraph.pregel.remote import RemoteGraph

        rg = RemoteGraph("subgraph_demo", url=URL)

        # 1) plain invoke (the "ok" branch: prepare -> inner -> finalize)
        ok = rg.invoke({"text": "hello world"})
        assert ok["text"] == "[WORLD HELLO [PREPARED]] [finalized]", ok
        print(f"1) invoke (ok branch)     -> {ok['text']}")

        # 2) the conditional "reject" branch is reachable end-to-end
        rejected = rg.invoke({"text": ""})
        assert rejected["text"] == "[rejected: empty input] [finalized]", rejected
        print(f"2) invoke (reject branch) -> {rejected['text']}")

        # 3) RemoteGraph subgraph control: inner subgraph node updates must
        #    surface as separately namespaced events through this server.
        namespaces = [
            ns
            for ns, _ in rg.stream({"text": "hello world"}, stream_mode="updates", subgraphs=True)
        ]
        inner = [ns for ns in namespaces if ns and any("inner" in part for part in ns)]
        assert inner, f"no namespaced inner subgraph events surfaced: {namespaces}"
        print(f"3) stream_subgraphs       -> inner namespace surfaced: {inner[0]}")

        print("\nOK: standalone agent server federates through RemoteGraph end-to-end")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    main()
