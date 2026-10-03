# Push Dashboard

A monolith app: FastAPI backend + React frontend, one Docker image, one
process, one port. GitHub pushes hit a webhook, get logged, and show up
on a live dashboard.

## What "monolith" means here, concretely

Unlike a microservices setup (separate containers for frontend/backend/db,
talking over a network), this is **one Python process** that:
1. Serves JSON from `/api/*` and `/webhook` (the backend).
2. Serves the **already-built** React static files for everything else
   (the frontend).

The React app is compiled (`npm run build`) once, during the Docker image
build — the running container never executes Node.js or compiles
anything. It just serves pre-built HTML/CSS/JS files directly from disk,
the same as any static site.

## How it works

### The webhook — verifying it's really from GitHub

`/webhook` is a public URL. Without verification, anyone who finds it
could POST a fake payload and inject fake data into your dashboard.
GitHub signs every webhook request with a secret you set — this app
recomputes that signature (`app/webhook.py`, HMAC-SHA256) and compares it
using `hmac.compare_digest` (a comparison that always takes the same
amount of time, so it can't leak information about *how close* a wrong
guess was — a regular `==` comparison can).

### The database

Plain SQLite via Python's built-in `sqlite3` module — no ORM, no separate
database container. The whole database is one file (`data/pushes.db`)
inside the container, tracked by a Docker volume so it survives restarts.
This is the deliberate trade-off that makes this a true single-container
monolith, unlike the earlier `local-stack` project which had a dedicated
Postgres container.

### The multi-stage Dockerfile

```dockerfile
FROM node:20-alpine AS frontend-build   # stage 1: build tools only
...
RUN npm run build

FROM python:3.12-slim                   # stage 2: what actually ships
...
COPY --from=frontend-build /frontend/dist ./frontend/dist
```

Stage 1 exists purely to produce `frontend/dist/` — the compiled static
files. Stage 2 copies *only that output* in, not Node.js, not
`node_modules`, not the JSX source. The final image has no JavaScript
toolchain in it at all, which keeps it smaller and means there's nothing
for someone to compile or tamper with at runtime.

### The catch-all frontend route

```python
@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    return FileResponse(FRONTEND_DIST / "index.html")
```

Any request that isn't `/api/*`, `/webhook`, or `/assets/*` falls through
to this and gets `index.html`. This dashboard doesn't use client-side
routing yet, but this is the standard pattern that makes it ready to add
pages later without touching the backend.

## Running it

### With Docker (production-like)

```bash
docker build -t push-dashboard .
docker run -p 8000:8000 \
  -e GITHUB_WEBHOOK_SECRET=your-secret-here \
  -v push_dashboard_data:/app/data \
  push-dashboard
```

Visit `http://localhost:8000`.

### Locally, for development (two terminals)

```bash
# Terminal 1: backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2: frontend (hot-reloading dev server)
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173` — Vite's dev server proxies `/api/*` and
`/webhook` to the FastAPI backend on `:8000` (see `vite.config.js`), so
the React code never needs to know it's talking cross-origin in dev.

## Wiring up a real GitHub webhook

1. Get this app reachable from the internet. For local testing, a tunnel
   tool (e.g. `ngrok http 8000` or `cloudflared tunnel --url http://localhost:8000`)
   gives you a temporary public URL.
2. On GitHub: repo → **Settings → Webhooks → Add webhook**.
   - Payload URL: `https://<your-tunnel-url>/webhook`
   - Content type: `application/json`
   - Secret: same value as your `GITHUB_WEBHOOK_SECRET` env var
   - Events: just "push" is enough
3. GitHub sends a `ping` event immediately to confirm the URL works — you
   should see `{"status": "pong"}` logged.
4. Push a commit and refresh the dashboard.

## API reference

```
POST   /webhook              GitHub webhook receiver
GET    /api/pushes           List pushes (query params: limit, offset, repo, branch, status)
GET    /api/pushes/{id}      Get one push's full detail
PATCH  /api/pushes/{id}      Update status: "pending" | "success" | "failed"
```

## Extending this project (toward the bigger idea)

This is intentionally the smallest useful slice. Natural next additions,
in roughly the order they'd build on each other:
- **Task list** — a second table, manually created todo items per repo,
  independent of pushes.
- **Push history retention cap** — trim to the last N pushes per repo.
- **Live preview** — the big one: on push, actually `git clone` +
  build the repo in an isolated container, and proxy to it. This is
  where the project stops being a monolith and grows back into a
  multi-container setup like `local-stack`.
- **GitHub OAuth login** — needed once this stops being single-user.

## Troubleshooting

- **Webhook returns 401** — your `GITHUB_WEBHOOK_SECRET` env var doesn't
  match the secret you set on GitHub's webhook settings page.
- **Dashboard shows nothing after a push** — check the container logs
  (`docker logs <container>`); a non-"push" event (like GitHub's initial
  ping) is expected to be ignored, but check `X-GitHub-Event` in your
  webhook's "Recent Deliveries" tab on GitHub if a real push isn't showing.
- **Database resets every restart** — make sure you're running with the
  `-v push_dashboard_data:/app/data` volume mount; without it, SQLite's
  file lives only in the container's throwaway layer.
