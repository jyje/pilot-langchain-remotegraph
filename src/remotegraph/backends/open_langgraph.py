from remotegraph.backends.base import REPO_ROOT, DockerComposeBackend


class OpenLangGraphBackend(DockerComposeBackend):
    """FastAPI + Postgres + Redis reimplementation of the LangGraph Platform API."""

    name = "open-langgraph"
    compose_file = REPO_ROOT / "docker" / "open-langgraph" / "docker-compose.yml"
    config_file = REPO_ROOT / "docker" / "open-langgraph" / "open_langgraph.json"
    base_url = "http://127.0.0.1:8001"
