"""people.session_version: signing out ends every session the person has

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-06
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Every session token carries the version it was issued under; logging out adds one, so older tokens stop working.
    # Existing rows start at 0, which is what a token issued before this column existed is treated as carrying.
    op.add_column("people", sa.Column("session_version", sa.Integer(), nullable=False, server_default=sa.text("0")))


def downgrade() -> None:
    op.drop_column("people", "session_version")
