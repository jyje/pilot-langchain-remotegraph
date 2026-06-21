from __future__ import annotations

import typer

from remotegraph.backends import BACKENDS
from remotegraph.settings import load_config, save_config

app = typer.Typer(help="Manage remotegraph configuration (remotegraph.toml).")


@app.command("show")
def show() -> None:
    """Print the current configuration."""
    config = load_config()
    for key, value in config.items():
        typer.echo(f"{key}: {value}")


@app.command("init")
def init() -> None:
    """Create remotegraph.toml with defaults if it doesn't exist yet."""
    config = load_config()
    save_config(config)
    typer.echo("Wrote remotegraph.toml")


@app.command("set")
def set_value(key: str, value: str) -> None:
    """Set a configuration key, e.g. `remotegraph config set active_backend aegra`."""
    if key == "active_backend" and value not in BACKENDS:
        raise typer.BadParameter(f"Unknown backend '{value}'. Choices: {', '.join(BACKENDS)}")
    config = load_config()
    config[key] = value
    save_config(config)
    typer.echo(f"Set {key} = {value}")
