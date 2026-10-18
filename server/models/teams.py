import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.config import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String)
    # NULL until a manager is assigned; unique, so a person runs at most one team.
    manager_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"), unique=True)
    active: Mapped[bool] = mapped_column(default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    manager = relationship("Person", foreign_keys=[manager_id], lazy="joined")

    __table_args__ = (Index("uq_teams_name_lower", func.lower(name), unique=True),)
