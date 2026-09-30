"""FastAPI app. Run from backend/:  uvicorn app.main:create_app --factory --reload

All routes are under /api. Teacher and child-mode routes need a teacher token
(POST /api/auth/login with TEACHER_PIN); the parent page is public by its
random link token. Audio and the SQLite database stay on this machine
for privacy. See docs/security.md.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import BACKEND_DIR
from .db import make_engine, session_factory
from .routes import auth, children, parent, reports, sessions, tests
from .security import SECURITY_HEADERS, AuthConfig, require_teacher
from .services.transcribe import cached_transcribe


def create_app(
    *,
    db_url: str | None = None,
    storage_dir: Path | None = None,
    transcriber=None,
    llm_client=None,
    teacher_pin: str | None = None,
    secret: str | None = None,
) -> FastAPI:
    load_dotenv(BACKEND_DIR.parent / ".env")
    load_dotenv(BACKEND_DIR / ".env")

    pin = teacher_pin or os.getenv("TEACHER_PIN") or ""
    key = secret or os.getenv("AKSHAR_SECRET") or ""
    if not pin or not key:
        raise RuntimeError(
            "TEACHER_PIN and AKSHAR_SECRET must be set (see .env.example). "
            'Generate a secret with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )

    show_docs = os.getenv("AKSHAR_API_DOCS", "false").lower() in ("1", "true", "yes")
    app = FastAPI(
        title="Akshar API",
        docs_url="/api/docs" if show_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if show_docs else None,
    )
    storage = Path(storage_dir or os.getenv("AKSHAR_STORAGE") or BACKEND_DIR / "storage")
    storage.mkdir(parents=True, exist_ok=True)
    engine = make_engine(db_url or os.getenv("AKSHAR_DB_URL") or f"sqlite:///{BACKEND_DIR / 'akshar.db'}")

    app.state.get_db = session_factory(engine)
    app.state.storage_dir = storage
    app.state.transcriber = transcriber or cached_transcribe
    app.state.llm_client = llm_client
    app.state.auth = AuthConfig(pin, key)

    origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    teacher = [Depends(require_teacher)]
    app.include_router(auth.router, prefix="/api")
    app.include_router(parent.router, prefix="/api")
    for r in (children.router, tests.router, sessions.router, reports.router):
        app.include_router(r, prefix="/api", dependencies=teacher)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    return app
