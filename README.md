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

## Quickstart (Docker Compose)

```bash
git clone <this-repo>
cd yt-downloader
cp .env.example .env
# Edit .env — at minimum set JWT_SECRET and AUTH_USERS.

docker compose up -d --build
# UI:  http://localhost/
# API: http://localhost/api
```

Default credentials from `.env.example` are `admin / changeme` — **change them
before exposing the app**. Multiple users may be configured as
`alice:secret1,bob:secret2` (you can also use bcrypt hashes generated via
`htpasswd -nbB user pass`).

### Services

| Service | Purpose |
| --- | --- |
| `valkey` | Redis-compatible queue + progress store |
| `backend` | FastAPI HTTP API |
| `worker` | RQ worker (replicas: 2 → matches the 2-job concurrency cap) |
| `cleanup` | Sweeper that deletes files older than 10 min every 2 min |
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
