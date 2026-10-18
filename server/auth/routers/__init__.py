"""The auth feature's endpoints as one router. `server/main.py` mounts it under `/api`."""
from fastapi import APIRouter

from auth.routers import google

router = APIRouter()
router.include_router(google.router)
