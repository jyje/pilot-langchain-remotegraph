"""Declarative workflow/subgraph-workflow topology loader.

Defines a graph's nodes and edges in YAML (or JSON -- PyYAML parses JSON
unchanged, so no separate branch is needed) instead of imperative
`.add_node()`/`.add_edge()` calls. A node can be a plain function (`fn:`, a
dotted `"package.module:attr"` import path) or another workflow file
(`workflow:`), which is loaded recursively and added as a compiled subgraph
node -- the same node-is-a-compiled-graph composition verified in
agents/subgraph_demo.

    nodes:
      - name: validate
        fn: agents.subgraph_demo.nodes:validate
      - name: inner
        workflow: agents/subgraph_demo/inner_workflow.yaml
    edges:
      - [__start__, validate]
      - conditional:
          source: validate
          fn: agents.subgraph_demo.nodes:route_after_validate
          targets: {ok: transform, invalid: reject}
      - [transform, __end__]
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, TypedDict

import yaml
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

_SENTINELS = {"__start__": START, "__end__": END}


def _resolve(ref: str) -> Any:
    """Resolve a "package.module:attr" reference (dotted Python import path)."""
    module_path, _, attr = ref.partition(":")
    module = importlib.import_module(module_path)
    return getattr(module, attr)


def _node_target(node_name: str) -> str:
    return _SENTINELS.get(node_name, node_name)  # type: ignore[return-value]


def load_workflow(path: str | Path) -> CompiledStateGraph:
    """Load a workflow/subgraph-workflow spec and compile it into a graph."""
    path = Path(path)
    spec = yaml.safe_load(path.read_text())

    state_keys = spec["state_keys"]
    fields = {k: Any for k in state_keys}
    state_schema = TypedDict(spec.get("name", "WorkflowState"), fields)  # ty: ignore[invalid-argument-type] -- dynamic TypedDict, fields not known statically

    builder = StateGraph(state_schema)  # ty: ignore[invalid-argument-type] -- known ty false positive on TypedDict vs StateT bound

    for node in spec["nodes"]:
        name = node["name"]
        if "fn" in node:
            builder.add_node(name, _resolve(node["fn"]))
        elif "workflow" in node:
            nested_path = (path.parent / node["workflow"]).resolve()
            builder.add_node(name, load_workflow(nested_path))
        else:
            raise ValueError(f"Node {name!r} must declare either 'fn' or 'workflow'")

    for edge in spec["edges"]:
        if isinstance(edge, dict):
            cond = edge["conditional"]
            targets = {key: _node_target(value) for key, value in cond["targets"].items()}
            builder.add_conditional_edges(
                _node_target(cond["source"]), _resolve(cond["fn"]), targets
            )
        else:
            source, target = edge
            builder.add_edge(_node_target(source), _node_target(target))

    return builder.compile()  # ty: ignore[invalid-return-type] -- dynamic state schema, generic params not known statically
