#!/usr/bin/env bash
# Local + Docker cleanup before git push. Safe to re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "==> Project cleanup in $ROOT"

# Python / tooling artifacts (not useful for git push)
rm -rf \
  .venv \
  .pytest_cache \
  .mypy_cache \
  .ruff_cache \
  .coverage \
  htmlcov \
  .tox \
  .eggs \
  dist \
  build

find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
find . -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '.DS_Store' -o -name '*.log' \) -delete 2>/dev/null || true

# Secrets / env files that must never be pushed
for f in .env .env.local .env.*.local credentials.json secrets.json .secrets; do
  if [[ -e "$f" ]]; then
    echo "    removing secret/env file: $f"
    rm -f "$f"
  fi
done
find . -maxdepth 2 -type f \( -name '*.pem' -o -name 'id_rsa' -o -name 'id_rsa.pub' -o -name '*.key' \) ! -path './.git/*' -print -delete 2>/dev/null || true

# Lesson artifact listed in .gitignore
rm -f scoping-pack.md 2>/dev/null || true

echo "==> Local junk removed"

# Docker: stop project-related containers, then prune unused resources
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo "==> Docker cleanup"

  # Stop & remove any containers whose name/label mentions this lesson
  mapfile -t lesson_ids < <(docker ps -aq --filter "name=lesson-02" --filter "name=surviving-the-network" 2>/dev/null || true)
  if ((${#lesson_ids[@]})); then
    echo "    stopping/removing lesson containers..."
    docker stop "${lesson_ids[@]}" >/dev/null 2>&1 || true
    docker rm -f "${lesson_ids[@]}" >/dev/null 2>&1 || true
  fi

  # Compose down if a compose file exists
  if [[ -f docker-compose.yml || -f docker-compose.yaml || -f compose.yml || -f compose.yaml ]]; then
    docker compose down --remove-orphans 2>/dev/null || docker-compose down --remove-orphans 2>/dev/null || true
  fi

  echo "    pruning stopped containers, unused networks, dangling images, build cache..."
  docker container prune -f
  docker network prune -f
  docker image prune -f
  docker builder prune -f 2>/dev/null || true
  # Unused (not just dangling) images — frees more disk; leave volumes alone unless dangling
  docker image prune -a -f 2>/dev/null || true
  docker volume prune -f

  echo "==> Docker cleanup done"
  docker system df 2>/dev/null || true
else
  echo "==> Docker not available or not running — skipped container/image prune"
fi

echo "==> Cleanup complete. Tree ready for git push (run: git status)."
