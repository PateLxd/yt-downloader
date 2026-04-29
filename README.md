# Private YouTube Downloader (yt-dlp + Valkey + RQ)

A modern, private-use web app that lets authenticated users download YouTube
videos and audio with `yt-dlp`. Jobs run through a Valkey-backed RQ queue with
strict concurrency, rate limits, and 10-minute file lifetimes — sized for a
2-core Ubuntu VPS.

## Stack

| Layer | Tech |
| --- | --- |
| Frontend | Next.js 14 (App Router), Tailwind CSS, shadcn-style components |
| Backend | FastAPI, Pydantic v2, JWT auth |
| Queue | Valkey + Python RQ |
| Downloader | yt-dlp + ffmpeg |
| Reverse proxy | nginx |
| Orchestration | Docker Compose |

## Features

- 🔗 URL → metadata extraction (title, thumbnail, duration, formats)
- 🎥 Video download with quality presets (4K / 1080p / 480p / custom) — defaults to MP4
- 🎧 Audio extraction to MP3 at 64 / 128 / 192 / 320 kbps
- ✂️ Custom time-range clipping via `yt-dlp --download-sections`
- 📥 Real-time progress (percent, speed, ETA) via Valkey-backed status, polled by the UI
- 🔐 JWT auth with env-seeded users (plaintext or bcrypt hashes)
- 🚦 Concurrency cap (default **2 jobs**) — extra requests get `please wait for some time`
- ⏱️ Per-user rate limit (**5/hour** by default)
- 🗑️ `/tmp/downloads` files auto-deleted after **10 minutes** by the `cleanup` service (host crontab also supported)

## Quickstart on a fresh VPS

```bash
git clone https://github.com/PateLxd/yt-downloader.git
cd yt-downloader
./scripts/setup.sh         # installs Docker, generates a JWT secret, brings up the stack
```

This is idempotent — re-running is safe. After it finishes, the app is on
`http://<your-vps-ip>/` with default creds `admin / changeme`. Edit `.env`
(`AUTH_USERS=...`) and `docker compose restart backend` to change them
**before exposing the app to the internet**. Multiple users:
`AUTH_USERS=alice:secret1,bob:secret2` (you can also use bcrypt hashes via
`htpasswd -nbB user pass`).

### Re-deploy after code changes

```bash
./scripts/deploy.sh        # git pull + rebuild + rolling restart on origin/main
```

Override branch with `DEPLOY_BRANCH=staging ./scripts/deploy.sh`. Force a redeploy on the same commit with `FORCE=1 ./scripts/deploy.sh`.

### Quickstart (manual, if you don't want the script)

```bash
cp .env.example .env       # edit JWT_SECRET and AUTH_USERS
docker compose up -d --build
# UI:  http://localhost/
# API: http://localhost/api
```

### YouTube cookies (recommended on cloud VPS IPs)

YouTube increasingly challenges anonymous yt-dlp requests with
*"Sign in to confirm you're not a bot"*. Workaround: export a Netscape
`cookies.txt` from a logged-in browser (e.g. Chrome extension
*Get cookies.txt LOCALLY*), then:

```bash
mv ~/Downloads/cookies.txt ./secrets/cookies.txt
sed -i 's|^YT_DLP_COOKIES_PATH=.*|YT_DLP_COOKIES_PATH=/run/cookies.txt|' .env
docker compose restart backend worker
# Tell git to ignore your local edits to the placeholder (prevents accidental commits):
git update-index --skip-worktree secrets/cookies.txt
```

The file is bind-mounted into both `backend` and `worker` containers at
`/run/cookies.txt`. The repo ships an empty `secrets/cookies.txt` placeholder
so the bind mount always resolves to a file — overwrite it with your real
cookies. `secrets/cookies.txt.example` documents the expected format.

When yt-dlp later starts hitting the bot challenge again (cookies expired,
Google rotated session), you can paste a fresh export straight into the UI:
the *Update cookies* button on a failed job — or the link next to
*Recent downloads* — opens a modal that POSTs the new cookies to
`/api/auth/cookies`. They're stored in Valkey with a 7-day TTL
(`COOKIES_OVERRIDE_TTL_SECONDS`) and override the on-disk file until they
expire.

### Auto-refreshing cookies (opt-in)

If you'd rather not re-export cookies manually every few weeks, there's an
optional `cookie-refresh` service that uses headless Chromium (Playwright)
to keep the YouTube session warm:

```bash
# .env
COMPOSE_PROFILES=cookie-refresh
docker compose up -d
```

What it does on each cycle (default: every 6h, configurable via
`COOKIE_REFRESH_INTERVAL_SECONDS`):

1. **Logged-in keep-alive** — boots Chromium with the existing
   `secrets/cookies.txt` (or a previously-saved Playwright profile in
   `secrets/yt-state/`), visits `youtube.com/feed/subscriptions`, confirms
   we're still authenticated, and plays a short video to extend the
   session.
2. **Anonymous fallback** — if the keep-alive detects we've been signed
   out (Google forced re-auth), it falls back to visiting YouTube
   anonymously, accepting the EU consent dialog, and at least getting
   the consent + visitor cookies. You'll see a `WARNING` in the logs
   when this happens — that's your cue to re-upload a real cookies.txt.
3. Refreshed cookies are written to **both** `secrets/cookies.txt` (so
   they survive restarts) **and** the Valkey runtime override (so the
   next download picks them up without a restart).

Caveats:

- The Playwright image is ~1.5 GB. If disk is tight on your VPS, leave
  the service disabled and use the *paste cookies in the UI* flow above
  instead.
- The first run needs an existing `secrets/cookies.txt` to bootstrap
  the logged-in session — the service can't log into Google for you.
- Watch the logs after the first run to see whether the keep-alive
  succeeded:
  ```bash
  docker compose logs cookie-refresh | tail -30
  ```
  You're looking for `Detected signed-in YouTube session` and
  `__Secure-1PSID expires at <date>` entries. Anything else means it
  fell back to anonymous.

### Services

| Service | Purpose |
| --- | --- |
| `valkey` | Redis-compatible queue + progress store |
| `backend` | FastAPI HTTP API |
| `worker` | RQ worker (replicas: 2 → matches the 2-job concurrency cap) |
| `cleanup` | Sweeper that deletes files older than 10 min every 2 min |
| `cookie-refresh` | (opt-in) Playwright service that warms the YouTube session every 6h |
| `frontend` | Next.js standalone server |
| `nginx` | Reverse proxy on port 80 |

### Tuning concurrency

The 2-job cap is enforced both in the API (refuses with HTTP 503 when full)
and structurally — there are 2 worker replicas, each pulling 1 job at a time.
To raise the cap on a beefier VPS:

```yaml
# docker-compose.yml
worker:
  deploy:
    replicas: 4   # also bump MAX_CONCURRENT_JOBS in .env
```

## Local development

### Backend

```bash
cd backend
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"

# Spin up Valkey separately:
docker run -d --rm -p 6379:6379 valkey/valkey:8-alpine

export REDIS_URL=redis://localhost:6379/0
export AUTH_USERS=admin:admin
export JWT_SECRET=dev-secret

# Run API + worker in two terminals
uvicorn app.main:app --reload
python worker.py
```

### Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000/api npm run dev
```

### Tests

```bash
cd backend && pytest
```

## API surface

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/api/auth/login` | `{ username, password }` → `{ access_token }` |
| `POST` | `/api/metadata` | `{ url }` → metadata + formats |
| `POST` | `/api/downloads` | Submit a job (gated by capacity + rate limit) |
| `GET` | `/api/downloads` | List the caller's jobs |
| `GET` | `/api/downloads/{id}` | Job status + progress |
| `GET` | `/api/downloads/{id}/file` | Stream the produced file (auth required) |
| `GET` | `/api/capacity` | `{ busy, active_jobs, max_jobs }` for the UI banner |
| `GET` | `/api/usage` | Caller's hourly quota usage |
| `GET` | `/health` | Liveness |

## Resource protection

- `MAX_CONCURRENT_JOBS` (default 2) — overflow returns `503 please wait for some time`
- `MAX_VIDEO_SECONDS` (default 7200) — yt-dlp `match_filter` rejects long videos
- `RATE_LIMIT_PER_HOUR` (default 5) — sliding window kept in Valkey
- `FILE_TTL_SECONDS` (default 600) — `cleanup` service + matching cron snippet in `scripts/cleanup-cron.sh`

## Notes

- This downloader is intended for **private/personal** use. Respect YouTube's
  Terms of Service and copyright laws.
- Files are written to a Docker volume (`downloads`) mounted at
  `/tmp/downloads` in the backend, worker, and cleanup containers.
- Tokens live in `localStorage` and are sent as `Authorization: Bearer …`.
