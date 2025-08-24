.ONESHELL:
release:
	@version="$$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')"; \
	if [ -z "$$version" ]; then echo "Error: project.version not found in pyproject.toml"; exit 1; fi; \
	git tag -a "v$$version" -m "Release v$$version"; \
	git push origin HEAD --tags
