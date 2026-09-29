# Lesson 1 — everything runs locally. No API keys, no services, no network.
.PHONY: help install test run write lint check clean

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n",$$1,$$2}'

install:   ## create .venv and install dependencies
	python3 -m venv .venv
	./.venv/bin/pip install --upgrade pip
	./.venv/bin/pip install -r requirements.txt

test:      ## run the suite with coverage
	./.venv/bin/python -m pytest tests/ -v --cov=src --cov-report=term-missing --cov-fail-under=90

run:       ## measure the baseline and print the scoping pack
	./.venv/bin/python -m src.main

write:     ## write scoping-pack.md
	./.venv/bin/python -m src.main --write

lint:      ## type check and lint
	./.venv/bin/python -m mypy src/ tests/ --ignore-missing-imports
	./.venv/bin/python -m ruff check src/ tests/

check: test lint ## everything this lesson must pass
	@echo "Lesson 1 green."

clean:
	rm -rf .venv .pytest_cache .coverage htmlcov scoping-pack.md
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
