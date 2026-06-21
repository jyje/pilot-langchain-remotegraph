"""RemoteGraph round-trip smoke tests against each live backend.

These are opt-in: each test is skipped unless the corresponding backend is
already running (`remotegraph host up <backend>` + `remotegraph agent deploy
<backend>`) and reachable. They are not part of the default CI run -- they
exercise real Docker containers / local LLM servers that aren't available
there.
"""

from __future__ import annotations

import pytest
import requests

from remotegraph.backends import get_backend


def _is_reachable(base_url: str) -> bool:
    try:
        requests.get(f"{base_url}/health", timeout=2)
    except requests.RequestException:
        return False
    return True


@pytest.mark.parametrize("backend_name", ["aegra", "open-langgraph", "langgraph-platform"])
def test_remotegraph_round_trip(backend_name: str) -> None:
    backend = get_backend(backend_name)
    if not _is_reachable(backend.base_url):
        pytest.skip(
            f"{backend_name} not reachable at {backend.base_url} -- "
            f"run `remotegraph host up {backend_name} && "
            f"remotegraph agent deploy {backend_name}` first"
        )

    from langgraph.pregel.remote import RemoteGraph

    remote = RemoteGraph("coder", url=backend.base_url)
    result = remote.invoke(
        {"messages": [{"role": "user", "content": "What is 2 + 2? Just the number."}]}
    )

    assert "4" in result["messages"][-1]["content"]
