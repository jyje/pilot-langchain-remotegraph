"""Dummy node functions for tests/test_workflow.py."""

from __future__ import annotations


def add_one(state: dict) -> dict:
    return {"n": state["n"] + 1}


def double(state: dict) -> dict:
    return {"n": state["n"] * 2}


def route(state: dict) -> str:
    return "big" if state["n"] > 5 else "small"
