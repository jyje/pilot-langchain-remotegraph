from __future__ import annotations

import typer

from remotegraph.backends import BACKENDS, get_backend
from remotegraph.settings import get_active_backend

app = typer.Typer(help="Start, stop, and inspect backend hosting stacks.")

BackendArg = typer.Argument(None, help="Backend name (defaults to the active backend).")


def _resolve(backend: str | None) -> str:
    return backend or get_active_backend()


@app.command("list")
def list_backends() -> None:
    """List the available backends and which one is active."""
    active = get_active_backend()
    for name in BACKENDS:
        marker = "*" if name == active else " "
        typer.echo(f"{marker} {name}")


@app.command("up")
def up(backend: str | None = BackendArg) -> None:
    """Start a backend's hosting stack."""
    name = _resolve(backend)
    b = get_backend(name)
    if b.requires_license:
        typer.echo(
            f"Note: {name} needs an Enterprise license for Docker; using license-free dev mode."
        )
    b.up()
    typer.echo(f"{name} is up at {b.base_url}")


@app.command("down")
def down(backend: str | None = BackendArg) -> None:
    """Stop a backend's hosting stack."""
    name = _resolve(backend)
    get_backend(name).down()
    typer.echo(f"{name} is down")


@app.command("status")
def status(backend: str | None = BackendArg) -> None:
    """Show whether a backend is running."""
    name = _resolve(backend)
    typer.echo(get_backend(name).status())


@app.command("logs")
def logs(backend: str | None = BackendArg) -> None:
    """Stream a backend's logs."""
    name = _resolve(backend)
    get_backend(name).logs()
