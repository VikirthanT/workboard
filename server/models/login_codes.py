import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from database.config import Base


class LoginCode(Base):
    """A one-time code that Google sign-in hands the browser in the address (`/login?code=...`). The browser trades it,
    once, for a session token, so the token itself never appears in a URL, the history or a log.
    Only a hash of the code is stored, so a leaked database cannot be used to sign in."""

    __tablename__ = "login_codes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    code_hash: Mapped[str] = mapped_column(String, unique=True)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
