"""identity tables: people, teams, access_audit_log

Revision ID: 0001
Revises:
Create Date: 2026-10-16
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UUID_DEFAULT = sa.text("gen_random_uuid()")
NOW = sa.text("now()")


def upgrade() -> None:
    # people.team_id and teams.manager_id point at each other, so people is created first
    # and its team foreign key is added after teams exists.
    op.create_table(
        "people",
        sa.Column("id", sa.Uuid(), server_default=UUID_DEFAULT, primary_key=True),
        sa.Column("slack_user_id", sa.String(), nullable=False, unique=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint("role in ('member', 'manager')", name="ck_people_role"),
        # The allowed domain is app config (ALLOWED_EMAIL_DOMAIN), so only the case is checked here.
        sa.CheckConstraint("email = lower(email)", name="ck_people_email_lower"),
    )
    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(), server_default=UUID_DEFAULT, primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("manager_id", sa.Uuid(), sa.ForeignKey("people.id", ondelete="SET NULL"), nullable=True, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    )
    op.create_foreign_key("fk_people_team_id", "people", "teams", ["team_id"], ["id"], ondelete="SET NULL")
    op.create_index("uq_teams_name_lower", "teams", [sa.text("lower(name)")], unique=True)
    op.create_index(
        "uq_people_one_manager_per_team",
        "people",
        ["team_id"],
        unique=True,
        postgresql_where=sa.text("role = 'manager'"),
    )
    op.create_table(
        "access_audit_log",
        sa.Column("id", sa.Uuid(), server_default=UUID_DEFAULT, primary_key=True),
        # No foreign keys on purpose: the table is append-only, so nothing may rewrite its rows.
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("person_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    )
    # Append-only is enforced here, not just by the app: any UPDATE or DELETE on a row is refused, whoever runs it.
    # TRUNCATE is not a row operation and is not caught; production should not grant TRUNCATE to the app role.
    op.execute(
        """
        CREATE FUNCTION access_audit_log_refuse_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'access_audit_log is append-only (% refused)', TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER access_audit_log_append_only
        BEFORE UPDATE OR DELETE ON access_audit_log
        FOR EACH ROW EXECUTE FUNCTION access_audit_log_refuse_change()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER access_audit_log_append_only ON access_audit_log")
    op.execute("DROP FUNCTION access_audit_log_refuse_change()")
    op.drop_table("access_audit_log")
    op.drop_index("uq_people_one_manager_per_team", table_name="people")
    op.drop_index("uq_teams_name_lower", table_name="teams")
    op.drop_constraint("fk_people_team_id", "people", type_="foreignkey")
    op.drop_table("teams")
    op.drop_table("people")
