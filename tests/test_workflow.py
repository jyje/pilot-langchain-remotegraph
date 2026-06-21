from __future__ import annotations

import pytest

from remotegraph.workflow import load_workflow


def _write(path, content: str) -> None:
    path.write_text(content)


def test_conditional_edge_routes_correctly(tmp_path) -> None:
    spec = tmp_path / "spec.yaml"
    _write(
        spec,
        """
        name: test_wf
        state_keys: [n]
        nodes:
          - name: add_one
            fn: tests.fixtures.workflow_nodes:add_one
          - name: double
            fn: tests.fixtures.workflow_nodes:double
        edges:
          - [__start__, add_one]
          - conditional:
              source: add_one
              fn: tests.fixtures.workflow_nodes:route
              targets: {big: double, small: __end__}
          - [double, __end__]
        """,
    )
    graph = load_workflow(spec)

    assert graph.invoke({"n": 10}) == {"n": 22}  # 10 -> 11 (big) -> 22
    assert graph.invoke({"n": 1}) == {"n": 2}  # 1 -> 2 (small) -> stop


def test_nested_workflow_node_becomes_a_subgraph(tmp_path) -> None:
    inner = tmp_path / "inner.yaml"
    _write(
        inner,
        """
        name: inner_wf
        state_keys: [n]
        nodes:
          - name: double
            fn: tests.fixtures.workflow_nodes:double
        edges:
          - [__start__, double]
          - [double, __end__]
        """,
    )
    outer = tmp_path / "outer.yaml"
    _write(
        outer,
        """
        name: outer_wf
        state_keys: [n]
        nodes:
          - name: add_one
            fn: tests.fixtures.workflow_nodes:add_one
          - name: inner
            workflow: inner.yaml
        edges:
          - [__start__, add_one]
          - [add_one, inner]
          - [inner, __end__]
        """,
    )
    graph = load_workflow(outer)

    assert graph.invoke({"n": 3}) == {"n": 8}  # 3 -> 4 (add_one) -> 8 (inner: double)

    node_names = set(graph.get_graph(xray=True).nodes)
    assert any(name.startswith("inner:") for name in node_names), (
        "expected the nested workflow's node to appear namespaced under 'inner:', "
        f"got {node_names}"
    )


def test_node_without_fn_or_workflow_raises(tmp_path) -> None:
    spec = tmp_path / "bad.yaml"
    _write(
        spec,
        """
        name: bad_wf
        state_keys: [n]
        nodes:
          - name: mystery
        edges:
          - [__start__, mystery]
          - [mystery, __end__]
        """,
    )
    with pytest.raises(ValueError, match="must declare either"):
        load_workflow(spec)


def test_research_pipeline_yaml_matches_supervisor_graph() -> None:
    from agents.supervisor.graph import graph as supervisor_graph

    wf = load_workflow("agents/workflows/research_pipeline.yaml")

    def edge_set(g):
        gg = g.get_graph()
        return {n.id for n in gg.nodes.values()}, {(e.source, e.target) for e in gg.edges}

    assert edge_set(wf) == edge_set(supervisor_graph)
