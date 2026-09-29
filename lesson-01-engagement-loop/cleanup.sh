#!/usr/bin/env bash
# Cleanup local artifacts that should not be git-pushed, strip secrets,
# and prune unused Docker resources.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "==> Repo root: $ROOT"

# ---------------------------------------------------------------------------
# 1. Remove local build / cache / generated artifacts (already in .gitignore)
# ---------------------------------------------------------------------------
echo "==> Removing cache, venv, coverage, and generated files..."

rm -rf \
  .venv \
  .pytest_cache \
  .mypy_cache \
  .ruff_cache \
  htmlcov \
  dist \
  build \
  .eggs
rm -rf ./*.egg-info ./**/*.egg-info 2>/dev/null || true

# Bytecode / coverage / generated scoping pack
find . -type d -name '__pycache__' -print0 2>/dev/null | xargs -0 rm -rf 2>/dev/null || true
find . -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '.coverage' -o -name 'coverage.xml' \) -delete 2>/dev/null || true
rm -f .coverage scoping-pack.md

# OS junk
find . -type f \( -name '.DS_Store' -o -name 'Thumbs.db' \) -delete 2>/dev/null || true

# ---------------------------------------------------------------------------
# 2. Remove secret / env files that must never be pushed
# ---------------------------------------------------------------------------
echo "==> Scanning for and removing secret/env files..."

SECRET_GLOBS=(
  .env
  .env.*
  *.pem
  *.key
  id_rsa
  id_ed25519
  credentials.json
  service-account*.json
)

removed_secrets=0
for pattern in "${SECRET_GLOBS[@]}"; do
  # shellcheck disable=SC2086
  while IFS= read -r -d '' f; do
    # Keep example templates
    case "$f" in
      *.example|*.sample|*.template) continue ;;
    esac
    echo "    removing secret file: $f"
    rm -f "$f"
    removed_secrets=$((removed_secrets + 1))
  done < <(find . -maxdepth 3 -type f -name "$pattern" -print0 2>/dev/null || true)
done

if [[ "$removed_secrets" -eq 0 ]]; then
  echo "    no secret/env files found"
fi

# ---------------------------------------------------------------------------
# 3. Docker: stop running containers, remove unused resources
# ---------------------------------------------------------------------------
resolve_docker() {
  if command -v docker >/dev/null 2>&1; then
    command -v docker
    return 0
  fi
  # WSL often has Docker Desktop on the Windows side only
  for candidate in \
    "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe" \
    "/mnt/c/Program Files/Docker/Docker/resources/bin/docker" \
    docker.exe; do
    if command -v "$candidate" >/dev/null 2>&1 || [[ -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

echo "==> Docker cleanup..."
if DOCKER_BIN="$(resolve_docker)"; then
  echo "    using: $DOCKER_BIN"
  if ! "$DOCKER_BIN" info >/dev/null 2>&1; then
    echo "    Docker daemon not reachable — skipping container/image prune"
  else
    # Stop all running containers
    running="$("$DOCKER_BIN" ps -q 2>/dev/null || true)"
    if [[ -n "${running}" ]]; then
      echo "    stopping running containers..."
      # shellcheck disable=SC2086
      "$DOCKER_BIN" stop $running
    else
      echo "    no running containers"
    fi

    # Remove stopped containers, unused networks, dangling images, build cache
    echo "    pruning unused containers, networks, images, and build cache..."
    "$DOCKER_BIN" system prune -af --volumes

    echo "    Docker cleanup done"
  fi
else
  echo "    docker not found — skipping"
fi

echo "==> Cleanup complete. Safe to git add / push source files only."
