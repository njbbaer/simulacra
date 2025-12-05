#!/usr/bin/env bash

set -e

if [ $# -ne 1 ]; then
    echo "Usage: $0 {major|minor|patch}"
    exit 1
fi

bump_type="$1"

if [[ ! "$bump_type" =~ ^(major|minor|patch)$ ]]; then
    echo "Error: argument must be 'major', 'minor', or 'patch'"
    exit 1
fi

current_version=$(grep -oP '^version = "\K[^"]+' pyproject.toml)

if [ -z "$current_version" ]; then
    echo "Error: could not read version from pyproject.toml"
    exit 1
fi

IFS='.' read -r major minor patch <<< "$current_version"

case "$bump_type" in
    major)
        major=$((major + 1))
        minor=0
        patch=0
        ;;
    minor)
        minor=$((minor + 1))
        patch=0
        ;;
    patch)
        patch=$((patch + 1))
        ;;
esac

new_version="$major.$minor.$patch"

echo "Running tests..."
make test

echo "Bumping version from $current_version to $new_version"

sed -i "s/^version = .*/version = \"$new_version\"/" pyproject.toml
uv sync
git add pyproject.toml uv.lock
git commit -m "Release v$new_version"
git tag -a "v$new_version" -m "Release v$new_version"
git push origin HEAD --tags

echo "Released v$new_version"
