#!/usr/bin/env bash
# Clean local junk (not useful for git push), scan for secrets, and prune Docker.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

log() { printf '==> %s\n' "$*"; }
warn() { printf '!!  %s\n' "$*" >&2; }

resolve_docker() {
  if command -v docker >/dev/null 2>&1; then
    # Prefer a real Linux docker over the WSL stub that only prints advice.
    local candidate
    candidate="$(command -v docker)"
    if "$candidate" version >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  fi
  local win="/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe"
  if [[ -x "$win" ]] && "$win" version >/dev/null 2>&1; then
    printf '%s\n' "$win"
    return 0
  fi
  return 1
}

log "Cleaning Python / tooling artifacts in $ROOT"
rm -rf \
  .venv \
  .pytest_cache \
  .mypy_cache \
  .ruff_cache \
  htmlcov \
  .tox \
  dist \
  build \
  .coverage \
  coverage.xml \
  .DS_Store

find . -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find . -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '.coverage.*' \) -delete 2>/dev/null || true

log "Removing local secret / env files if present"
# Never keep credentials in a tree you intend to push.
for path in .env .env.local .env.production credentials.json secrets.json; do
  if [[ -e "$path" ]]; then
    warn "Removing $path"
    rm -f "$path"
  fi
done

log "Scanning tracked-looking sources for likely API keys"
# Soft scan only — refuse to print matches that look like live secrets.
if command -v rg >/dev/null 2>&1; then
  if rg -n --hidden \
      -g '!.venv/**' -g '!.git/**' -g '!cleanup.sh' \
      -e 'sk-[A-Za-z0-9]{20,}' \
      -e 'AKIA[0-9A-Z]{16}' \
      -e 'api[_-]?key\s*[:=]\s*['\''\"]?[A-Za-z0-9_-]{16,}' \
      . >/tmp/lesson04-secret-scan.txt 2>/dev/null; then
    warn "Possible secrets found (review /tmp/lesson04-secret-scan.txt):"
    cat /tmp/lesson04-secret-scan.txt >&2 || true
  else
    log "No obvious API key patterns found"
    rm -f /tmp/lesson04-secret-scan.txt
  fi
else
  warn "rg not installed; skipped secret scan"
fi

log "Cleaning leftover Ollama download scraps in /tmp (if any)"
rm -f /tmp/ollama.tgz /tmp/ollama-linux-amd64.tar.zst 2>/dev/null || true

log "Docker: stop containers and remove unused resources"
if DOCKER_BIN="$(resolve_docker)"; then
  log "Using docker: $DOCKER_BIN"
  # Stop every running container.
  running="$("$DOCKER_BIN" ps -q 2>/dev/null || true)"
  if [[ -n "${running}" ]]; then
    log "Stopping running containers"
    # shellcheck disable=SC2086
    "$DOCKER_BIN" stop $running >/dev/null || true
  fi
  # Remove every container (running or stopped).
  all_containers="$("$DOCKER_BIN" ps -aq 2>/dev/null || true)"
  if [[ -n "${all_containers}" ]]; then
    log "Removing all containers"
    # shellcheck disable=SC2086
    "$DOCKER_BIN" rm -f $all_containers >/dev/null || true
  fi
  log "docker container prune"
  "$DOCKER_BIN" container prune -f || true
  log "docker image prune (all unused images)"
  "$DOCKER_BIN" image prune -a -f || true
  log "docker volume prune"
  "$DOCKER_BIN" volume prune -f || true
  log "docker network prune"
  "$DOCKER_BIN" network prune -f || true
  log "docker system prune (unused + build cache)"
  "$DOCKER_BIN" system prune -a -f --volumes || true
else
  warn "Docker daemon not reachable — skipped container/image cleanup"
fi

log "Done. Tree is ready for git add / push (re-run make install before budget/load)."
