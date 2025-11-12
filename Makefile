.PHONY: run test lint release

run:
	uv run app.py

test:
	uv run pytest

lint:
	uv run pre-commit run --all-files

release:
	./release.sh $(type)
