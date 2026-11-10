"""All the tasks feature's endpoints as one router: the board, the reports, and the task endpoints.
Each lives in its own file next to this one; `server/main.py` mounts this under `/api`."""
from fastapi import APIRouter

from tasks.routers import board, imports, reports, tasks

router = APIRouter()
router.include_router(board.router)
router.include_router(reports.router)
router.include_router(imports.router)  # before tasks: `/tasks/import/...` must not match `/tasks/{id}`
router.include_router(tasks.router)
