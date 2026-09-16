# Contributing

Thanks for considering a contribution to favorites-manager!

## Setup

```bash
git clone https://github.com/tuanductran/favorites-manager.git
cd favorites-manager
uv venv
uv pip install -e ".[dev]"
```

## Running tests

```bash
.venv/bin/pytest -q
```

## Project layout

See the "Project structure" section in [README.md](README.md) for what
each module is responsible for.

## Guidelines

- Keep modules focused: parsing, writing, deduping, organizing, and
  per-browser export each live in their own file.
- Add a test in `tests/` for any parser/writer edge case you fix — the
  Netscape Bookmark format is unforgiving about unclosed tags, so
  regressions are easy to introduce silently.
- Run the test suite against the minimum supported Python version (3.9)
  before submitting a PR, since the codebase uses
  `from __future__ import annotations` to allow modern type-hint syntax
  there.

## Reporting issues

Please include:
- The command you ran and its output
- A minimal bookmark HTML snippet that reproduces the issue, if relevant
- Your Python version and OS
