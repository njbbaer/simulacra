## Agent Instructions

### Commands

- Run all Python commands with `uv run`.
- Install dependencies with `uv add <package>`.
- Lint and format with `make lint`.
- Run tests with `uv run pytest`.

### Code Style

- Keep the code clean and minimal by avoiding unnecessary complexity.
- Use comments sparingly only to clarify unintuitive sections.
- Group public methods first, followed by private methods.
- Prefix private methods and variables with an underscore.
- Add types where sensible, but avoid overly verbose annotations.
- Place higher-level methods before the lower-level methods they call.

### Other

- Do not write tests unless explicitly instructed.
