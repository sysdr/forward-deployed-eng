# Lesson 05. `make check` needs no services and no network.
.PHONY: help install test lint check clean run widen costs
MODEL ?= llama3.2:3b

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-9s\033[0m %s\n",$$1,$$2}'

install:  ## create .venv and install dependencies
	python3 -m venv .venv
	./.venv/bin/pip install --upgrade pip
	./.venv/bin/pip install -r requirements.txt

test:     ## unit tests. No model, no network.
	./.venv/bin/python -m pytest tests/ -v --cov=src --cov-report=term-missing --cov-fail-under=90

lint:     ## types and style
	./.venv/bin/python -m mypy src/ tests/ --ignore-missing-imports
	./.venv/bin/python -m ruff check src/ tests/

check: test lint ## everything that must pass before publishing
	@echo "Lesson green."

clean:
	rm -rf .venv .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

run:      ## score the guard against every scenario. No model, no network.
	./.venv/bin/python -m src.main

widen:    ## the same run with one path added to the policy and nothing else changed
	./.venv/bin/python -m src.main --allow "services/search-gateway/**"

costs:    ## lesson 4's priced run, still here
	./.venv/bin/python -m src.main --budget --model $(MODEL)

