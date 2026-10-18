"""The Alembic migrations, run on a scratch database of their own (not the one the other tests use).

The whole suite already builds its schema from the migrations; these tests check the things that only show
when you go the other way: downgrading cleanly, upgrading again, no drift from the models, and a single head.
"""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util import CommandError
from sqlalchemy import create_engine, inspect, text

from core.config import settings
from tests.conftest import BASE_URL

SCRATCH = "workboard_migration_test"
TABLES = {"people", "teams", "access_audit_log", "tasks", "task_activity", "login_codes"}
SERVER_DIR = Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    config = Config(str(SERVER_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(SERVER_DIR / "migrations"))
    return config


@pytest.fixture
def scratch(monkeypatch):
    """An empty database, with the app's settings pointed at it for the length of the test."""
    admin = create_engine(BASE_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {SCRATCH}"))
    url = BASE_URL.set(database=SCRATCH)
    monkeypatch.setattr(settings, "database_url", url.render_as_string(hide_password=False))
    engine = create_engine(url)
    yield engine
    engine.dispose()
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {SCRATCH} WITH (FORCE)"))


def tables(engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def audit_trigger_function_exists(engine) -> bool:
    with engine.connect() as conn:
        return bool(conn.scalar(text("SELECT count(*) FROM pg_proc WHERE proname = 'access_audit_log_refuse_change'")))


def test_there_is_exactly_one_migration_head():
    # Two heads would mean two people branched the history; upgrade would then refuse to run.
    assert len(ScriptDirectory.from_config(alembic_config()).get_heads()) == 1


def test_upgrade_creates_every_table_and_the_audit_trigger(scratch):
    assert tables(scratch) == set()

    command.upgrade(alembic_config(), "head")

    assert tables(scratch) == TABLES | {"alembic_version"}
    assert audit_trigger_function_exists(scratch)


def test_downgrade_removes_everything_it_created(scratch):
    command.upgrade(alembic_config(), "head")

    command.downgrade(alembic_config(), "base")

    assert tables(scratch) == {"alembic_version"}
    assert not audit_trigger_function_exists(scratch)


def test_upgrade_downgrade_upgrade_ends_where_it_started(scratch):
    config = alembic_config()
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    assert tables(scratch) == TABLES | {"alembic_version"}
    with scratch.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM pg_indexes WHERE indexname = 'uq_people_one_manager_per_team'")) == 1


def test_upgrading_twice_is_a_harmless_no_op(scratch):
    config = alembic_config()
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    assert tables(scratch) == TABLES | {"alembic_version"}


def test_the_models_and_the_migrations_agree(scratch):
    """The same check as `alembic check`: autogenerate would find nothing to add, drop or change."""
    command.upgrade(alembic_config(), "head")
    command.check(alembic_config())  # raises if the models and the migrated schema differ


def test_the_drift_check_really_does_catch_a_difference(scratch):
    """Guards the test above: a schema edited by hand must make the check fail, or it proves nothing."""
    command.upgrade(alembic_config(), "head")
    with scratch.begin() as conn:
        conn.execute(text("ALTER TABLE people ADD COLUMN sneaked_in text"))

    with pytest.raises(CommandError, match="New upgrade operations detected"):
        command.check(alembic_config())
