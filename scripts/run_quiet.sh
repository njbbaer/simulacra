#!/usr/bin/env bash
set -euo pipefail

description="$1"
shift
tmp_file=$(mktemp)
trap 'rm -f "$tmp_file"' EXIT

if "$@" > "$tmp_file" 2>&1; then
    printf "  ✓ %s\n" "$description"
else
    exit_code=$?
    printf "  ✗ %s\n" "$description"
    cat "$tmp_file"
    exit $exit_code
fi
