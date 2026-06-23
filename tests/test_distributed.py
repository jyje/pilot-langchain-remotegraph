from __future__ import annotations

import json

import pytest

from remotegraph import distributed


def test_agent_ports_increment_from_base() -> None:
    assert distributed.agent_port("researcher") == 2027
    assert distributed.agent_port("coder") == 2028
    assert distributed.agent_port("reviewer") == 2029


def test_agent_port_unknown_name_lists_supported_agents() -> None:
    with pytest.raises(ValueError, match="Supported agents: researcher, coder, reviewer"):
        distributed.agent_port("planner")


def test_agent_ports_respect_custom_base() -> None:
    assert distributed.agent_port("researcher", base_port=9000) == 9000
    assert distributed.agent_port("reviewer", base_port=9000) == 9002


def test_project_name_is_namespaced_per_agent() -> None:
    assert distributed.project_name("coder") == "remotegraph-coder"


def test_compose_command_isolates_project_and_uses_distributed_file() -> None:
    cmd = distributed.compose_command("coder", 2028, "up", "-d")
    assert cmd[:5] == ["docker", "compose", "-p", "remotegraph-coder", "-f"]
    assert cmd[5].endswith("docker-compose.distributed.yml")
    assert cmd[-2:] == ["up", "-d"]


def test_compose_env_carries_port_and_config() -> None:
    env = distributed.compose_env("coder", 2028)
    assert env["AEGRA_PORT"] == "2028"
    assert env["AGENT_NAME"] == "coder"
    assert env["AGENT_CONFIG"].endswith("aegra.coder.json")


def test_write_agent_config_is_single_graph(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(distributed, "CONFIG_DIR", tmp_path)
    path = distributed.write_agent_config("coder", "agents/coder/graph.py:graph")

    written = json.loads(path.read_text())
    assert written["dependencies"] == ["."]
    assert written["graphs"] == {"coder": "agents/coder/graph.py:graph"}


def test_urls_map_to_supervisor_env_vars() -> None:
    urls = distributed.urls()
    assert urls == {
        "RESEARCHER_URL": "http://127.0.0.1:2027",
        "CODER_URL": "http://127.0.0.1:2028",
        "REVIEWER_URL": "http://127.0.0.1:2029",
    }
