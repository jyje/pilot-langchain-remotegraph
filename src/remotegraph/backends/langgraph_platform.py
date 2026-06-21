"""LangGraph Platform self-hosted.

`langgraph up` (the dockerized standalone server) requires an Enterprise
`LANGGRAPH_CLOUD_LICENSE_KEY`, which is impractical for a free pilot. This
backend instead runs `langgraph dev` as a subprocess: a license-free,
in-memory server that exposes the identical assistants/threads/runs REST API,
so `RemoteGraph`/`langgraph_sdk` connect to it exactly as they would to a
Docker-hosted or Cloud deployment.
"""

from __future__ import annotations

import json
import subprocess

from remotegraph.backends.base import REPO_ROOT

STATE_DIR = REPO_ROOT / ".remotegraph"
PID_FILE = STATE_DIR / "langgraph-platform.pid"
LOG_FILE = STATE_DIR / "langgraph-platform.log"
CONFIG_FILE = REPO_ROOT / "langgraph.json"


class LangGraphPlatformBackend:
    name = "langgraph-platform"
    base_url = "http://127.0.0.1:2024"
    requires_license = True  # only for the full `langgraph up` Docker path, not `langgraph dev`

    def up(self) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        port = self.base_url.rsplit(":", 1)[1]
        with LOG_FILE.open("w") as log:
            process = subprocess.Popen(
                ["uv", "run", "langgraph", "dev", "--port", port, "--no-browser"],
                cwd=REPO_ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        PID_FILE.write_text(str(process.pid))

    def down(self) -> None:
        if not PID_FILE.exists():
            return
        pid = int(PID_FILE.read_text())
        subprocess.run(["kill", str(pid)], check=False)
        PID_FILE.unlink(missing_ok=True)

    def status(self) -> str:
        if not PID_FILE.exists():
            return "stopped"
        pid = int(PID_FILE.read_text())
        alive = subprocess.run(["kill", "-0", str(pid)], check=False).returncode == 0
        return "running" if alive else "stopped"

    def logs(self) -> None:
        if LOG_FILE.exists():
            subprocess.run(["tail", "-f", str(LOG_FILE)], check=False)

    def deploy(self, agents: dict[str, str]) -> None:
        CONFIG_FILE.write_text(
            json.dumps({"dependencies": ["."], "graphs": agents, "env": ".env"}, indent=2) + "\n"
        )
