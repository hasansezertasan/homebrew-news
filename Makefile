.DEFAULT_GOAL := check
.PHONY: sync generate validate lint test build check

sync:
	uv sync --locked

generate: sync
	uv run ai-rulez generate --no-local
	uv run ai-rulez generate --plugin --no-local

validate: sync
	uv run ai-rulez validate
	uv run ai-rulez verify --plugin
	uv run python -m scripts.check_repository

lint: sync
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src scripts tests

test: sync
	uv run pytest -n auto

build: sync
	uv build
	uv build .hermes/package --out-dir dist/hermes

check: validate lint test build
