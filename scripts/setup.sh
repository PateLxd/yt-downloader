#!/usr/bin/env bash
# One-shot bootstrap for a fresh Ubuntu VPS (22.04 / 24.04).
#
# What it does:
#   1. Installs Docker Engine + Compose plugin (idempotent — skips if present)
#   2. Adds the invoking user to the `docker` group (so subsequent runs don't need sudo)
#   3. Ensures .env exists (copies from .env.example) and prompts you to edit critical fields
#   4. Ensures secrets/cookies.txt exists (empty placeholder, so the compose mount works)
#   5. Builds + brings up the stack
#   6. Waits for /health and the frontend to respond, then prints next steps
#
# Re-runs are safe.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m  %s\n'  "$*" >&2; }
die()  { printf '\033[1;31mxx\033[0m  %s\n'  "$*" >&2; exit 1; }

# 1. Docker
if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker Engine + Compose plugin"
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl gnupg
  sudo install -m 0755 -d /etc/apt/keyrings
  if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
      | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
  fi
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  log "Docker already installed: $(docker --version)"
fi

# 2. docker group membership
if ! id -nG "$USER" | grep -qw docker; then
  log "Adding $USER to docker group (you'll need to log out/in for this to take effect)"
  sudo usermod -aG docker "$USER"
  warn "Group membership only applies to *new* shells. For this run we'll keep using sudo."
  DOCKER="sudo docker"
else
  DOCKER="docker"
fi

# 3. .env
if [[ ! -f .env ]]; then
  log "Creating .env from .env.example"
  cp .env.example .env
  # Generate a real JWT secret (don't ship the placeholder).
  if command -v openssl >/dev/null 2>&1; then
    JWT_SECRET=$(openssl rand -hex 32)
    sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" .env
    log "Generated a random JWT_SECRET"
  fi
  warn "Edit .env now to set AUTH_USERS (default is admin:changeme — change before exposing)"
fi

# 4. cookies placeholder
# secrets/cookies.txt is committed as an empty file so the docker-compose bind
# mount always resolves to a file (not a Docker-created directory). Re-create
# it only if a checkout/clone problem dropped it.
mkdir -p secrets
if [[ ! -f secrets/cookies.txt ]]; then
  : > secrets/cookies.txt
  log "Created empty secrets/cookies.txt"
fi

# 5. Build + up
log "Building images"
$DOCKER compose build

log "Starting stack"
$DOCKER compose up -d

# 6. Health wait
log "Waiting for backend /health"
for i in {1..30}; do
  if $DOCKER compose exec -T backend curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    log "Backend is healthy"
    break
  fi
  sleep 1
  [[ $i == 30 ]] && die "Backend did not become healthy in 30s. Run: $DOCKER compose logs backend"
done

log "Waiting for nginx to serve the frontend on :80"
for i in {1..30}; do
  if curl -fsS -o /dev/null -w '' http://localhost/ 2>/dev/null; then
    log "nginx is serving the app"
    break
  fi
  sleep 1
  [[ $i == 30 ]] && warn "nginx not responding on :80 after 30s. Check: $DOCKER compose logs nginx"
done

GREEN=$'\033[1;32m'
RESET=$'\033[0m'
cat <<EOF

${GREEN}Setup complete.${RESET}

Stack:
  - Frontend + API:   http://$(hostname -I | awk '{print $1}')/        (nginx :80)
  - Default login:    admin / changeme   ← change AUTH_USERS in .env

Useful commands:
  $DOCKER compose ps                # status of all services
  $DOCKER compose logs -f backend   # tail backend logs
  $DOCKER compose logs -f worker    # tail worker logs
  ./scripts/deploy.sh               # pull latest main and re-deploy

YouTube tip:
  If yt-dlp hits 'Sign in to confirm you're not a bot', export a Netscape
  cookies.txt from a logged-in browser, save it to ./secrets/cookies.txt,
  set YT_DLP_COOKIES_PATH=/run/cookies.txt in .env, and restart with:
    $DOCKER compose restart backend worker
EOF
