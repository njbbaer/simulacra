.PHONY: run test lint release

run:
	uv run app.py

test:
	uv run pytest

lint:
	uv run pre-commit run --all-files

.ONESHELL:
release:
	@if [ -z "$(version)" ]; then echo "Usage: make release version=1.2.3"; exit 1; fi
	@echo "$(version)" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$$' || \
		{ echo "Error: version must be in format X.Y.Z"; exit 1; }
	sed -i 's/^version = .*/version = "$(version)"/' pyproject.toml
	uv sync
	git add pyproject.toml uv.lock
	git commit -m "Release v$(version)"
	git tag -a "v$(version)" -m "Release v$(version)"
	git push origin HEAD --tags
