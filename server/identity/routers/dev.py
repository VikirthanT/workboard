"""Dev sign-in list. Not part of the product: it exists only while DEV_AUTH is on, and is a 404 otherwise."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.config import settings
from core.exceptions import AppError
from database.config import get_db
from identity import schemas
from identity.services import dev_accounts

router = APIRouter(tags=["dev"])


@router.get("/dev/accounts", response_model=list[schemas.DevAccount])
def list_accounts(db: Session = Depends(get_db)):
    """Needs no sign-in (it is what the login page shows before anyone has), so it must not exist in production."""
    if not settings.dev_auth:
        raise AppError("not_found", "Not found.", 404)
    return [schemas.DevAccount(email=p.email, name=p.name, can_sign_in=ok) for p, ok in dev_accounts.list_dev_accounts(db)]
