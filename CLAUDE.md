# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

`pilot-langchain-remotegraph` is a pilot CLI (`remotegraph`, built with Typer/Ruff/ty on Python 3.14, packaged via `uv`) that tests LangGraph's `RemoteGraph` against three self-hosted, LangGraph-Platform-API-compatible backends: `aegra` (Docker), `open-langgraph-platform` (Docker, vendored as a git submodule fork under `vendor/` with local upstream bug fixes), and LangGraph Platform self-hosted (run via license-free `langgraph dev`, not Docker). Four example agents live under `agents/`: `researcher`/`coder`/`reviewer` are deployed to a backend; `supervisor` runs locally and calls them via `RemoteGraph`. See `README.md` for the full architecture, CLI reference, and known upstream issues.

Build/test commands: `uv run remotegraph --help`, `uv run ruff check .`, `uv run ty check`, `uv run pytest tests/`.

## Skills available

Two skills from `jyje/skills` are installed under `.agents/skills/` (tracked in `skills-lock.json`):

- `centered-readme` — formats README headers as a centered hero block (title, logo, tagline, badges, language links) matching jyje's standard repo style. Use when creating or restyling this repo's README.
- `git-commit-helper` — defines the commit message policy for this repo. Follow it for every commit:
  - Format: `<gitmoji> <type>(<domain>): <title>` plus an optional body explaining why.
  - Type/gitmoji must come from the mapping in `.agents/skills/git-commit-helper/SKILL.md` (e.g. `🎉 init`, `✨ feat`, `🐛 bug`, `♻️ refactor`, `📄 docs`).
  - Commit messages and explanations are English only.
  - Never run `git commit` or `git push` without explicit user approval first.
