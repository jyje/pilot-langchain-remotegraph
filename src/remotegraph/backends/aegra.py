from remotegraph.backends.base import REPO_ROOT, DockerComposeBackend


class AegraBackend(DockerComposeBackend):
    """aegra: FastAPI + Postgres + Redis exposing the LangGraph Platform API."""

    name = "aegra"
    compose_file = REPO_ROOT / "docker" / "aegra" / "docker-compose.yml"
    config_file = REPO_ROOT / "docker" / "aegra" / "aegra.json"
    base_url = "http://127.0.0.1:2026"
