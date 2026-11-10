"""Sign out: end the caller's sessions."""
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from auth.services import sessions
from database.config import get_db
from models import Person
from security.authentication import get_current_person

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(db: Session = Depends(get_db), actor: Person = Depends(get_current_person)):
    """End every session this person has, on every browser: the tokens already issued stop working at once.

    Who: any signed-in person. Returns 204. A token that is already dead gets the usual 401, which is fine: it is
    dead either way. (The development header sign-in has no token, so there is nothing for this to end.)
    """
    sessions.end_sessions(db, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
