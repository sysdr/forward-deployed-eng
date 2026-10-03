# Lesson 3. `make check` needs no services and no network.
# `make eval` talks to the remote Ollama host in EVAL_OLLAMA_HOST.
# Do not name that variable OLLAMA_HOST: a shell export of OLLAMA_HOST
# (common after installing Ollama) would override Make's ?= and send
# requests to localhost instead of the remote machine.
.PHONY: help install test lint gate check eval baseline clean

MODEL ?= llama3.1:8b
EVAL_OLLAMA_HOST ?= http://192.168.1.10:11434

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

gate:     ## fail if the golden set regressed. Uses the oracle, so it is offline.
	./.venv/bin/python -m src.main --model oracle --gate

check: test lint gate ## everything that must pass before publishing
	@echo "Lesson 3 green."

eval:     ## run the golden set against the model at EVAL_OLLAMA_HOST
	OLLAMA_HOST=$(EVAL_OLLAMA_HOST) ./.venv/bin/python -m src.main --model $(MODEL)

baseline: ## rewrite evals/baseline.json from the oracle run
	./.venv/bin/python -m src.main --model oracle --save-baseline

clean:
	rm -rf .venv .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
