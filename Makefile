.PHONY: run test lint release agent-test agent-lint

run:
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
