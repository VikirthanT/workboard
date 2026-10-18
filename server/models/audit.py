import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.config import Base


class AccessAuditLog(Base):
    """Append-only record of team and membership changes. A database trigger (migration 0001) refuses UPDATE and
    DELETE. actor_id, team_id and person_id carry no foreign key on purpose: a foreign key would have to rewrite
    or block rows when a person or team is deleted, which the trigger forbids."""

    __tablename__ = "access_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column()
    action: Mapped[str] = mapped_column(String)
    team_id: Mapped[uuid.UUID | None] = mapped_column()
    person_id: Mapped[uuid.UUID | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(String)
    details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
