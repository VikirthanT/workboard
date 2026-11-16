"""teams.standup_synced_at: when the team's standups were last read, even when no post was found

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-15
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("standup_synced_at", sa.DateTime(timezone=True), nullable=True))
    # Until now the "last sync" was the newest post read, so start from that.
    op.execute(
        "UPDATE teams SET standup_synced_at = latest.at FROM "
        "(SELECT team_id, max(read_at) AS at FROM standup_reads GROUP BY team_id) AS latest WHERE teams.id = latest.team_id"
    )


def downgrade() -> None:
    op.drop_column("teams", "standup_synced_at")
