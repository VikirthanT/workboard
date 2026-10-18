"""All the identity feature's endpoints as one router: teams and their members, people and the audit log, and the
development-only sign-in list. Each lives in its own file next to this one; `server/main.py` mounts this under `/api`."""
from fastapi import APIRouter

from identity.routers import dev, people, teams

router = APIRouter()
router.include_router(teams.router)
router.include_router(people.router)
router.include_router(dev.router)
