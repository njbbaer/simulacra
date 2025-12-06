## Agent Instructions

### Commands

- Run all Python commands with `uv run`.
- Install dependencies with `uv add <package>`.
- Lint and format with `make lint`.
- Run tests with `uv run pytest`.

### Code Style

- Keep the code clean and minimal by avoiding unnecessary complexity.
- Use comments sparingly only to clarify unintuitive sections.
- Prefix private methods and variables with an underscore.
- Add types where sensible, but avoid overly verbose annotations.

### Method Ordering

1. Constructor (`__init__`)
2. Public methods (higher-level before lower-level)
3. Public properties
4. Private methods (higher-level before lower-level)
5. Private properties
6. Class methods (`@classmethod`)
7. Static methods (`@staticmethod`)

### Other

- Do not write tests unless explicitly instructed.
