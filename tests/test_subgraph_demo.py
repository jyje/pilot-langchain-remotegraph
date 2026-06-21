from __future__ import annotations

from agents.subgraph_demo.graph import graph


def test_non_empty_text_goes_through_transform_branch() -> None:
    result = graph.invoke({"text": "hello world"})
    assert result["text"] == "[WORLD HELLO [PREPARED]] [finalized]"


def test_empty_text_goes_through_reject_branch() -> None:
    result = graph.invoke({"text": "   "})
    assert result["text"] == "[rejected: empty input] [finalized]"
