"""Subgraph demo: a deterministic, LLM-free graph with an actual subgraph node,
defined declaratively via workflow.yaml + inner_workflow.yaml (see
src/remotegraph/workflow.py).

Exists to verify, against a real backend, that RemoteGraph's
`stream_subgraphs` and `interrupt_before` work against a node that is itself
a compiled subgraph -- not just a plain function node. researcher/coder/
reviewer are flat ReAct agents and can't exercise this path. The inner
subgraph is itself a multi-step workflow with branching (validate -> reject
or transform -> format_text), not a single node, to also demonstrate the
"subgraph workflow pattern".
"""

from __future__ import annotations

from pathlib import Path

from remotegraph.workflow import load_workflow

graph = load_workflow(Path(__file__).parent / "workflow.yaml")
