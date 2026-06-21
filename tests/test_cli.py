from __future__ import annotations

from typer.testing import CliRunner

from remotegraph.cli import app

runner = CliRunner()


def test_root_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "config" in result.output
    assert "host" in result.output
    assert "agent" in result.output


def test_config_help() -> None:
    result = runner.invoke(app, ["config", "--help"])
    assert result.exit_code == 0
    assert "show" in result.output
    assert "set" in result.output


def test_host_help() -> None:
    result = runner.invoke(app, ["host", "--help"])
    assert result.exit_code == 0
    assert "up" in result.output
    assert "down" in result.output


def test_agent_help() -> None:
    result = runner.invoke(app, ["agent", "--help"])
    assert result.exit_code == 0
    assert "deploy" in result.output
    assert "call" in result.output


def test_host_list_shows_all_backends() -> None:
    result = runner.invoke(app, ["host", "list"])
    assert result.exit_code == 0
    assert "aegra" in result.output
    assert "open-langgraph" in result.output
    assert "langgraph-platform" in result.output


def test_config_set_unknown_backend_rejected() -> None:
    result = runner.invoke(app, ["config", "set", "active_backend", "not-a-backend"])
    assert result.exit_code != 0


def test_config_show_and_set_roundtrip(tmp_path, monkeypatch) -> None:
    from remotegraph import settings

    monkeypatch.setattr(settings, "CONFIG_FILE", tmp_path / "remotegraph.toml")

    result = runner.invoke(app, ["config", "set", "active_backend", "aegra"])
    assert result.exit_code == 0

    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "active_backend: aegra" in result.output
