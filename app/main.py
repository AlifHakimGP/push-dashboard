"""
main.py — the FastAPI app: API routes + serving the built React frontend.

THE "MONOLITH" PART
----------------------
This one process does two jobs at once:
  1. Serves JSON from /api/* and /webhook — the backend.
  2. Serves the pre-built React app's static files for everything else —
     the frontend.
There's no separate frontend server and no reverse proxy in front of this;
one `uvicorn` process, one port, one Docker container. The React files it
serves were already compiled (`npm run build`) during the Docker image
build — this app never runs Node or compiles anything at runtime.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import database
from .webhook import verify_signature

app = FastAPI(title="Push Dashboard")

# CORS is only needed for local development, where the React dev server
# (Vite, on port 5173) and this API (port 8000) are on different origins.
# In production, the frontend is served BY this same app on the same
# origin, so the browser never needs a cross-origin request at all — this
# middleware simply won't be exercised there.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_STATUSES = {"received", "pending", "success", "failed"}


@app.on_event("startup")
def on_startup():
    database.init_db()


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

@app.post("/webhook")
async def github_webhook(request: Request):
    body = await request.body()

    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if secret:
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(secret, body, signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type = request.headers.get("X-GitHub-Event", "")

    # GitHub sends a harmless "ping" event when you first set up a webhook,
    # just to confirm the URL is reachable — not an actual push.
    if event_type == "ping":
        return {"status": "pong"}

    if event_type != "push":
        return {"status": "ignored", "event": event_type}

    payload = await request.json()
    repo = payload.get("repository", {}).get("full_name", "unknown")
    branch = payload.get("ref", "").removeprefix("refs/heads/")
    head_commit = payload.get("head_commit") or {}
    commit_sha = head_commit.get("id", "")[:12]  # short SHA is enough to display
    commit_message = head_commit.get("message", "").splitlines()[0] if head_commit.get("message") else ""
    author = (head_commit.get("author") or {}).get("name", "unknown")
    pushed_at = head_commit.get("timestamp", "")

    push_id = database.insert_push(
        repo=repo,
        branch=branch,
        commit_sha=commit_sha,
        commit_message=commit_message,
        author=author,
        pushed_at=pushed_at,
        received_at=datetime.now(timezone.utc).isoformat(),
    )
    return {"status": "recorded", "id": push_id}


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

class StatusUpdate(BaseModel):
    status: str


@app.get("/api/pushes")
def api_list_pushes(limit: int = 50, offset: int = 0, repo: str | None = None,
                     branch: str | None = None, status: str | None = None):
    return database.list_pushes(limit=limit, offset=offset, repo=repo, branch=branch, status=status)


@app.get("/api/pushes/{push_id}")
def api_get_push(push_id: int):
    push = database.get_push(push_id)
    if push is None:
        raise HTTPException(status_code=404, detail="Push not found")
    return push


@app.patch("/api/pushes/{push_id}")
def api_update_status(push_id: int, body: StatusUpdate):
    if body.status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(ALLOWED_STATUSES)}",
        )
    updated = database.update_status(push_id, body.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Push not found")
    return database.get_push(push_id)


# ---------------------------------------------------------------------------
# Serving the built React frontend
# ---------------------------------------------------------------------------

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    # Vite builds assets (JS/CSS bundles) into a hashed-filename "assets"
    # subfolder — mount that directly so the browser can fetch them.
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        """
        Catch-all: any path that isn't /api/*, /webhook, or /assets/* falls
        through to here and gets index.html. This is what lets the React
        app handle its own routing client-side (not used by this simple
        single-page dashboard yet, but is the standard pattern so it's
        ready if you add pages later).
        """
        return FileResponse(FRONTEND_DIST / "index.html")
