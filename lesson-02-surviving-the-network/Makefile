# Lesson 2 — everything runs locally. The document store runs in-process.
# No API keys, no containers, no network beyond localhost.
.PHONY: help install test run noretry demo lint check clean

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n",$$1,$$2}'

install:   ## create .venv and install dependencies
	python3 -m venv .venv
	./.venv/bin/pip install --upgrade pip
	./.venv/bin/pip install -r requirements.txt

test:      ## run the suite with coverage
	./.venv/bin/python -m pytest tests/ -v --cov=src --cov-report=term-missing --cov-fail-under=90

run:       ## ingest from a store failing 30% of requests
	./.venv/bin/python -m src.main

noretry:   ## the same run with retries switched off
	./.venv/bin/python -m src.main --no-retry

demo:      ## what jitter does to a service coming back up
	./.venv/bin/python -m src.main --demo-jitter

lint:      ## type check and lint
	./.venv/bin/python -m mypy src/ tests/ --ignore-missing-imports
	./.venv/bin/python -m ruff check src/ tests/

check: test lint ## everything this lesson must pass
	@echo "Lesson 2 green."

clean:
	rm -rf .venv .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
