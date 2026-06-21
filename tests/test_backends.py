from __future__ import annotations

import json

import pytest

from remotegraph.backends import BACKENDS, get_backend
from remotegraph.backends.aegra import AegraBackend
from remotegraph.backends.langgraph_platform import LangGraphPlatformBackend
from remotegraph.backends.open_langgraph import OpenLangGraphBackend


@pytest.mark.parametrize(
    ("name", "expected_cls"),
    [
        ("aegra", AegraBackend),
        ("open-langgraph", OpenLangGraphBackend),
        ("langgraph-platform", LangGraphPlatformBackend),
    ],
)
def test_get_backend_returns_expected_type(name, expected_cls) -> None:
    assert isinstance(get_backend(name), expected_cls)


def test_get_backend_unknown_name_raises() -> None:
    with pytest.raises(ValueError, match="Unknown backend"):
        get_backend("not-a-backend")


def test_backends_registry_has_all_three() -> None:
    assert set(BACKENDS) == {"aegra", "open-langgraph", "langgraph-platform"}


def test_docker_compose_backend_deploy_writes_dependencies_and_graphs(tmp_path) -> None:
    backend = AegraBackend()
    backend.config_file = tmp_path / "aegra.json"

    backend.deploy({"researcher": "agents/researcher/graph.py:graph"})

    written = json.loads(backend.config_file.read_text())
    assert written["dependencies"] == ["."]
    assert written["graphs"] == {"researcher": "agents/researcher/graph.py:graph"}


def test_langgraph_platform_requires_license_for_docker_mode() -> None:
    assert LangGraphPlatformBackend.requires_license is True
    assert AegraBackend.requires_license is False
    assert OpenLangGraphBackend.requires_license is False
