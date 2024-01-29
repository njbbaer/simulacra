.ONESHELL:
release:
	@if [ -z "$(version)" ]; then \
		echo "Error: version is not set. Set it like 'make release version=X.X.X'"; \
		exit 1; \
	fi
	@if ! echo "$(version)" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$$'; then \
		echo "Error: version format is not correct. It should be 'X.X.X'"; \
		exit 1; \
	fi
	@git tag -a "v$(version)" -m "$message"
	@git push origin HEAD --tags

