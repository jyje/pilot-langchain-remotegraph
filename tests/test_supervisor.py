from __future__ import annotations

from agents.supervisor.graph import _remote


def _url_of(remote_graph) -> str:
    return str(remote_graph.sync_client.http.client.base_url)


def test_per_agent_url_env_var_wins(monkeypatch) -> None:
    monkeypatch.setenv("CODER_URL", "http://coder.internal:8000")
    monkeypatch.setenv("REMOTEGRAPH_BASE_URL", "http://shared.internal:9000")

    assert _url_of(_remote("coder")) == "http://coder.internal:8000"


def test_falls_back_to_shared_base_url(monkeypatch) -> None:
    monkeypatch.delenv("RESEARCHER_URL", raising=False)
    monkeypatch.setenv("REMOTEGRAPH_BASE_URL", "http://shared.internal:9000")

    assert _url_of(_remote("researcher")) == "http://shared.internal:9000"


def test_falls_back_to_default_when_nothing_set(monkeypatch) -> None:
    monkeypatch.delenv("REVIEWER_URL", raising=False)
    monkeypatch.delenv("REMOTEGRAPH_BASE_URL", raising=False)

    assert _url_of(_remote("reviewer")) == "http://localhost:2026"


def test_different_agents_can_use_different_servers(monkeypatch) -> None:
    monkeypatch.setenv("RESEARCHER_URL", "http://research.internal:8000")
    monkeypatch.setenv("CODER_URL", "http://coder.internal:8001")
    monkeypatch.delenv("REMOTEGRAPH_BASE_URL", raising=False)

    assert _url_of(_remote("researcher")) == "http://research.internal:8000"
    assert _url_of(_remote("coder")) == "http://coder.internal:8001"
