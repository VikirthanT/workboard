"""The standup channels the admin can give a team. Needs a signed-in person (401 otherwise).
Errors come back as {"detail": {"code", "message"}}; the codes are listed in `standups/README.md`."""
from fastapi import APIRouter, Depends

from models import Person
from security.authentication import get_current_person
from standups import schemas
from standups.services import channels

router = APIRouter(prefix="/standups", tags=["standups"])


@router.get("/channels", response_model=list[schemas.ChannelResponse])
def list_channels(actor: Person = Depends(get_current_person)):
    """Every channel in the standup app's database, by name, for the "standup channel" picker.

    Who: admins only (403 `forbidden`).
    Errors: 501 `standups_not_configured` when `STANDUP_DB_URL` is not set on this server.
    """
    return channels.list_channels(actor)
