#!/usr/bin/env bash
# Re-deploy on a host that already has the stack running.
#
# Pulls the latest commit on the configured branch, rebuilds images, and
# restarts services with as little downtime as possible.
#
# Re-runs are safe.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

BRANCH="${DEPLOY_BRANCH:-main}"
DOCKER="docker"
if ! id -nG "$USER" | grep -qw docker && [[ "$EUID" -ne 0 ]]; then
  DOCKER="sudo docker"
fi

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m  %s\n'  "$*" >&2; }
die()  { printf '\033[1;31mxx\033[0m  %s\n'  "$*" >&2; exit 1; }

# Sanity check
[[ -f docker-compose.yml ]] || die "docker-compose.yml not found in $REPO_DIR"
[[ -f .env ]]               || die ".env not found — run scripts/setup.sh first"

# 1. Pull latest
log "Fetching latest from origin/$BRANCH"
git fetch --prune origin "$BRANCH"
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [[ "$LOCAL" == "$REMOTE" ]]; then
  log "Already on $REMOTE — nothing to deploy"
  if [[ "${FORCE:-0}" != "1" ]]; then
    log "Set FORCE=1 ./scripts/deploy.sh to redeploy anyway."
    exit 0
  fi
fi

if [[ -n "$(git status --porcelain)" ]]; then
  warn "Working tree is dirty. Stash or commit before deploying."
  git status --short
  exit 1
fi

# Preserve any user-modified secrets across the reset. `git reset --hard`
# does NOT honor `--skip-worktree`, so without this it would silently restore
# the empty placeholder cookies.txt from origin and break YouTube downloads
# until the user re-uploads their cookies.
PRESERVED_DIR="$(mktemp -d)"
trap 'rm -rf "$PRESERVED_DIR"' EXIT
PRESERVED_FILES=(secrets/cookies.txt)
for f in "${PRESERVED_FILES[@]}"; do
  if [[ -s "$f" ]]; then
    mkdir -p "$PRESERVED_DIR/$(dirname "$f")"
    cp -p "$f" "$PRESERVED_DIR/$f"
  fi
done

log "Resetting to origin/$BRANCH"
git reset --hard "origin/$BRANCH"

# Restore preserved files (only those we actually saved — i.e. non-empty
# locally before the reset).
for f in "${PRESERVED_FILES[@]}"; do
  if [[ -f "$PRESERVED_DIR/$f" ]]; then
    cp -p "$PRESERVED_DIR/$f" "$f"
    log "Restored local $f across reset"
  fi
done

# 2. Build
log "Building images"
$DOCKER compose build --pull

# 3. Roll
# `up -d` with new images recreates only changed services. The worker has
# `replicas: 2` so Compose handles them; the API will have a brief blip.
log "Rolling stack to new images"
$DOCKER compose up -d --remove-orphans

# 4. Health
log "Waiting for backend /health"
for i in {1..45}; do
  if $DOCKER compose exec -T backend curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    log "Backend healthy"
    break
  fi
  sleep 1
  [[ $i == 45 ]] && die "Backend did not become healthy in 45s. Tail: $DOCKER compose logs --tail=200 backend"
done

# 5. Cleanup
log "Pruning dangling images"
$DOCKER image prune -f >/dev/null

NEW_REV=$(git rev-parse --short HEAD)
log "Deploy complete: now on $NEW_REV ($(git log -1 --format=%s))"
