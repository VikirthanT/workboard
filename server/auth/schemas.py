from pydantic import BaseModel


class SessionResponse(BaseModel):
    """What the browser keeps after signing in: the token it sends as `Authorization: Bearer`, and who it is."""

    token: str
    email: str
    name: str
