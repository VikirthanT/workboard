"""teams.standup_channel_id: which standup channel a team's suggestions are read from

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-13
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The standup app's channel id (a Slack channel id). NULL for every existing team: an admin sets it later.
    op.add_column("teams", sa.Column("standup_channel_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("teams", "standup_channel_id")
