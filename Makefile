.PHONY: app logs test lint test-quiet lint-quiet release

app:
	uv run app.py

logs:
	@journalctl --user --no-hostname -f _SYSTEMD_USER_UNIT=simulacra-dev.service

test:
	uv run pytest

lint:
	uv run ruff check --fix --unsafe-fixes
	uv run ruff format --quiet
	uv run mypy src tests

test-quiet:
	@./scripts/run_quiet.sh "tests" uv run pytest -q --no-header

lint-quiet:
	@./scripts/run_quiet.sh "lint" $(MAKE) --no-print-directory lint

release:
	./scripts/release.sh $(type)
