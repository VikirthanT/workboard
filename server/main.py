"""The Work Board API: where the app is put together.

Each feature (identity: people and teams; tasks: the board; auth: Google sign-in) owns its endpoints in its own
`routers/` folder; this file only mounts them all under `/api`. Errors raised anywhere as `AppError` are turned into
the same {"detail": {"code", "message"}} shape by `register_exception_handlers`. Settings come from environment
variables (see `core/config.py`). Who is calling is decided in `security/authentication.py`.
"""
from fastapi import FastAPI

from auth.routers import router as auth_router
from core.exceptions import register_exception_handlers
from identity.routers import router as identity_router
from tasks.routers import router as tasks_router

app = FastAPI(title="Work Board API")
register_exception_handlers(app)
app.include_router(identity_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(auth_router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    """Is the API up? Needs no sign-in, so a load balancer or a docker healthcheck can call it."""
    return {"status": "ok"}
