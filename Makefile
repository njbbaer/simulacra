.PHONY: app test lint test-quiet lint-quiet release

app:
	uv run app.py

test:
	uv run pytest

lint:
	uv run pre-commit run --all-files

test-quiet:
	@./scripts/run_quiet.sh "tests" uv run pytest -q --no-header --no-cov

lint-quiet:
	@./scripts/run_quiet.sh "lint" uv run pre-commit run --all-files

release:
	./scripts/release.sh $(type)
