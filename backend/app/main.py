from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import init_db
from app.observability import langfuse_status, shutdown_langfuse
from app.routers import clients, documents, recording, sessions


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield
    shutdown_langfuse()


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clients.router)
app.include_router(sessions.router)
app.include_router(recording.router)
app.include_router(documents.router)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "langfuse": langfuse_status(),
    }


# Production mode: serve the pre-built frontend (frontend/dist) when it exists,
# so Maria's install runs everything from a single server with no Node needed.
# In dev the dist folder is absent and Vite serves the frontend on :5173.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if FRONTEND_DIST.is_dir():  # pragma: no cover - absent in dev
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        # Real files (index.html, favicon, ...) are served as-is; every other
        # path falls back to index.html so React Router handles the route.
        file = (FRONTEND_DIST / path).resolve()
        if path and file.is_file() and file.is_relative_to(FRONTEND_DIST):
            return FileResponse(file)
        return FileResponse(FRONTEND_DIST / "index.html")
