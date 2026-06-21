"""Common interface implemented by every hostable backend."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Protocol

REPO_ROOT = Path(__file__).resolve().parents[3]


class Backend(Protocol):
    name: str
    base_url: str
    requires_license: bool

    def up(self) -> None: ...
    def down(self) -> None: ...
    def status(self) -> str: ...
    def logs(self) -> None: ...
    def deploy(self, agents: dict[str, str]) -> None: ...


class DockerComposeBackend:
    """A backend implemented as a docker compose stack with a graph-registration JSON file."""

    name: str
    compose_file: Path
    config_file: Path
    base_url: str
    requires_license = False

    def _compose(self, *args: str) -> list[str]:
        return ["docker", "compose", "-f", str(self.compose_file), *args]

    def up(self) -> None:
        subprocess.run(self._compose("up", "-d", "--build"), cwd=REPO_ROOT, check=True)

    def down(self) -> None:
        subprocess.run(self._compose("down"), cwd=REPO_ROOT, check=True)

    def status(self) -> str:
        result = subprocess.run(
            self._compose("ps"), cwd=REPO_ROOT, check=False, capture_output=True, text=True
        )
        return result.stdout.strip() or "stopped"

    def logs(self) -> None:
        subprocess.run(self._compose("logs", "-f"), cwd=REPO_ROOT, check=False)

    def deploy(self, agents: dict[str, str]) -> None:
        # "dependencies": ["."] puts the config file's own directory (the
        # container's /app, where agents/ is COPYed) on sys.path, so the
        # `from agents.llm import ...` absolute imports inside each graph
        # resolve correctly when the backend loads these files standalone.
        config = {"dependencies": ["."], "graphs": agents}
        self.config_file.write_text(json.dumps(config, indent=2) + "\n")
