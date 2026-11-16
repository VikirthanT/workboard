"""All the standups feature's endpoints as one router. Each lives in its own file next to this one;
`server/main.py` mounts this under `/api`."""
from fastapi import APIRouter

from standups.routers import channels, suggestions

router = APIRouter()
router.include_router(channels.router)
router.include_router(suggestions.router)
