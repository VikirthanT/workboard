"""The auth feature's endpoints as one router. `server/main.py` mounts it under `/api`."""
from fastapi import APIRouter

from auth.routers import google, session

router = APIRouter()
router.include_router(google.router)
router.include_router(session.router)
