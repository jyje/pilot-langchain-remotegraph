from remotegraph.backends.aegra import AegraBackend
from remotegraph.backends.base import Backend
from remotegraph.backends.langgraph_platform import LangGraphPlatformBackend
from remotegraph.backends.open_langgraph import OpenLangGraphBackend

BACKENDS: dict[str, type] = {
    "aegra": AegraBackend,
    "open-langgraph": OpenLangGraphBackend,
    "langgraph-platform": LangGraphPlatformBackend,
}


def get_backend(name: str) -> Backend:
    try:
        backend_cls = BACKENDS[name]
    except KeyError:
        raise ValueError(f"Unknown backend '{name}'. Choices: {', '.join(BACKENDS)}") from None
    return backend_cls()
