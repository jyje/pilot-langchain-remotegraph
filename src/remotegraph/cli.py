from __future__ import annotations

import typer

from remotegraph import agent, config, host

app = typer.Typer(
    name="remotegraph",
    help="Manage and test self-hosted LangGraph Platform-compatible backends via RemoteGraph.",
    no_args_is_help=True,
)
app.add_typer(config.app, name="config")
app.add_typer(host.app, name="host")
app.add_typer(agent.app, name="agent")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
