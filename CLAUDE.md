# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Guidelines

- Manage dependencies with `uv` and run all python commands with `uv run`
- Run tests with `uv run pytest` after making significant changes.
- Format code according to Black and Flake8 conventions.
- Group public methods first, followed by private methods.
- Prefix private methods and variables with an underscore.
