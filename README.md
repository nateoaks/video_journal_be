# Video Journal — Backend

This is a self-hosted personal video journal: a FastAPI backend paired with a Next.js
frontend, run together via Docker Compose on a single machine (Docker Desktop on macOS).
All media (clips, soundtracks, rendered compilations) and the SQLite database live on
bind-mounted host directories so data persists across container restarts and Mac reboots
with no extra configuration required.

## Prerequisites

> **This is the most common first-run failure point.** The frontend is built from a
> sibling repository. Both repos must be present before running `docker compose`.

- **Docker Desktop** installed and running on your Mac.
- The `video_journal_fe` repository cloned as a **sibling directory** next to this one:

  ```
  video_journal/
  ├── video_journal_be/   <- this repo
  └── video_journal_fe/   <- must exist here
  ```

  The `docker-compose.yml` uses `context: ../video_journal_fe` for the frontend build.
  If that directory is missing, the build fails immediately with a "context not found"
  error.

## Setup

```bash
docker compose up -d --build
```

That's it. Notes:

- **First build is slow** — FFmpeg is compiled into the backend image. Subsequent builds
  are fast unless dependencies change.
- **Migrations run automatically** at backend startup via Alembic. You do not need to run
  any `alembic` commands manually.
- **To customise settings** (e.g. `LOG_LEVEL`), edit the `environment:` block in
  `docker-compose.yml` directly and re-run `docker compose up -d`. The container reads
  its configuration from that block; a `.env` file on the host is not visible to the
  running container.

## Access

| What | URL |
|---|---|
| Frontend (the app) | http://localhost:3000 |
| API | http://localhost:8000/api/v1 |
| API docs (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

All ports are bound to `127.0.0.1` — local machine only. There is no authentication
layer. **Do not expose this stack publicly without adding authentication first.**

## Data and Backups

All persistent state lives in three host directories that are bind-mounted into the
backend container:

| Directory | Contents |
|---|---|
| `./data` | SQLite database (`journal.db`) and its WAL sidecar files (`journal.db-wal`, `journal.db-shm`) |
| `./media` | Uploaded video clips and soundtracks |
| `./outputs` | Rendered compilation MP4s |

**Safe backup procedure:**

```bash
docker compose down
tar czf journal-backup-$(date +%F).tgz data media outputs
docker compose up -d
```

> **Important:** Copying only `journal.db` without the WAL sidecar files
> (`journal.db-wal` and `journal.db-shm`) produces an **incomplete and potentially
> corrupt backup**. Always archive the entire `data/` directory.

Backup archives contain personal video and audio content. Store them somewhere secure
(encrypted volume, private cloud storage, etc.).

## Start on Login (Reboot Persistence)

To have the stack start automatically after a Mac reboot:

1. Open **Docker Desktop -> Settings -> General**.
2. Enable **"Start Docker Desktop when you sign in."**

Both containers have `restart: unless-stopped` in `docker-compose.yml`, so once Docker
Desktop is running they start automatically — no manual `docker compose up` needed after
a reboot.

See `docs/operations.md` for the full reboot and persistence verification runbook.

## Troubleshooting

**Frontend build fails with "context not found"**
The sibling `video_journal_fe` repo is not cloned. See [Prerequisites](#prerequisites).

**Port 3000 or 8000 already in use**
Find the conflicting process and stop it:

```bash
lsof -i :3000
lsof -i :8000
```

**Containers not starting after `docker compose up -d`**
Check container state and logs:

```bash
docker compose ps
docker compose logs backend
docker compose logs frontend
```

**Reset the stack without data loss**
`docker compose down` stops and removes containers but does **not** touch bind-mounted
directories. Your data is safe:

```bash
docker compose down && docker compose up -d
```
