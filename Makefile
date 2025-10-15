.ONESHELL:
release:
	@if [ -z "$(version)" ]; then echo "Usage: make release version=1.2.3"; exit 1; fi
	@sed -i 's/^version = .*/version = "$(version)"/' pyproject.toml
	@uv sync
	@git add pyproject.toml uv.lock
	@git commit -m "Release v$(version)"
	@git tag -a "v$(version)" -m "Release v$(version)"
	@git push origin HEAD --tags
