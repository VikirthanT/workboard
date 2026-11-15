"""The standup channels the admin can give a team. Needs a signed-in person (401 otherwise).
Errors come back as {"detail": {"code", "message"}}; the codes are listed in `standups/README.md`."""
from fastapi import APIRouter, Depends, Path

from models import Person
from security.authentication import get_current_person
from standups import schemas
from standups.services import channels

router = APIRouter(prefix="/standups", tags=["standups"])


@router.get("/channels", response_model=list[schemas.ChannelResponse])
def list_channels(actor: Person = Depends(get_current_person)):
    """Every channel in the standup app's database, by name, for the "standup channel" picker.

    Who: admins and managers (403 `forbidden`).
    Errors: 501 `standups_not_configured` when `STANDUP_DB_URL` is not set on this server.
    """
    return channels.list_channels(actor)


@router.get("/channels/{channel_id}", response_model=schemas.ChannelNameResponse)
def channel_name(
    channel_id: str = Path(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9]+$"),
    actor: Person = Depends(get_current_person),
):
    """The name Slack gives a channel id (the team page shows it beside the id). A query: it asks Slack and changes nothing.

    Who: admins and managers (403 `forbidden`).
    Errors: 404 `channel_not_found` (Slack cannot find it, or it is private and the bot is not in it); 409 `bot_not_in_channel`;
    501 `slack_not_configured`; 502 `slack_failed`; 422 for an id that is not letters and digits.
    """
    return schemas.ChannelNameResponse(id=channel_id, name=channels.channel_name(actor, channel_id))
