import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, false, func, text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.config import Base

ROLE_MEMBER = "member"
ROLE_MANAGER = "manager"


class Person(Base):
    """The directory (from the Slack user cache). Managers and admins are people too; only they can sign in."""

    __tablename__ = "people"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    slack_user_id: Mapped[str] = mapped_column(String, unique=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    # The team role. Admin is a separate switch so a person can be a member or manager and an admin at once.
    role: Mapped[str] = mapped_column(String, default=ROLE_MEMBER, server_default=ROLE_MEMBER)
    is_admin: Mapped[bool] = mapped_column(default=False, server_default=false())
    # NULL until someone puts the person on a team. A person is on at most one team.
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL", use_alter=True, name="fk_people_team_id")
    )
    active: Mapped[bool] = mapped_column(default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    team = relationship("Team", foreign_keys=[team_id], lazy="joined")

    __table_args__ = (
        CheckConstraint("role in ('member', 'manager')", name="ck_people_role"),
        # The allowed domain is app config (ALLOWED_EMAIL_DOMAIN), so only the case is checked here.
        CheckConstraint("email = lower(email)", name="ck_people_email_lower"),
        # At most one manager-role person per team (the "demote the old one first" order in the service keeps this satisfied).
        Index("uq_people_one_manager_per_team", "team_id", unique=True, postgresql_where=text("role = 'manager'")),
    )

    @property
    def team_name(self) -> str | None:
        return self.team.name if self.team else None
