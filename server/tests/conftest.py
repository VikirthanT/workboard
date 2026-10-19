"""Tests run against their own database (workboard_test_<pid>, one per run) built by the real Alembic migrations,
so a passing suite also proves the migrations produce a working schema."""
import os
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

if "DATABASE_URL" not in os.environ:
    pytest.exit(
        "DATABASE_URL is not set. Run the tests with `make server-test` (it loads .env, see .env.example). "
        "They use that server but their own database, workboard_test_<pid>.",
        returncode=2,
    )
BASE_URL = make_url(os.environ["DATABASE_URL"])
# One database per run (named by the process id), so two runs at once, say `make test` in two terminals, never drop or
# truncate each other's tables.
TEST_DB = f"workboard_test_{os.getpid()}"
TEST_URL = BASE_URL.set(database=TEST_DB)

# Must be set before anything imports core.config.
os.environ["DATABASE_URL"] = TEST_URL.render_as_string(hide_password=False)
os.environ["DEV_AUTH"] = "true"
# The app decides "today" with the server's own clock, and ATI is in India: run the tests in IST, as production does
# (Dockerfile.api), so they do not depend on where the developer's machine is.
os.environ["TZ"] = "Asia/Kolkata"
time.tzset()
# `make test` loads the developer's .env into this process. The tests must not depend on it (whether Google sign-in is
# set up on this machine, which domain or first admins it names, how long a session lasts), so every setting except
# the database is dropped here and the app's own defaults apply. A test that needs a setting sets it itself.
for _name in (
    "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI", "SECRET_KEY", "TOKEN_TTL_SECONDS",
    "ALLOWED_EMAIL_DOMAIN", "BOOTSTRAP_ADMIN_EMAILS",
):
    os.environ.pop(_name, None)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from database.config import SessionLocal  # noqa: E402
from main import app  # noqa: E402
from models import Person  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database():
    admin = create_engine(BASE_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
    # Absolute paths, so the suite runs the same from the repo root or from server/.
    server_dir = Path(__file__).resolve().parents[1]
    config = Config(str(server_dir / "alembic.ini"))
    config.set_main_option("script_location", str(server_dir / "migrations"))
    command.upgrade(config, "head")
    yield
    # The run's own database goes when the run ends. A run that was killed leaves its database behind; the next run
    # does not touch it (see the tests README for the one-line cleanup).
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    with SessionLocal() as db:
        db.execute(text("TRUNCATE access_audit_log, teams, people RESTART IDENTITY CASCADE"))
        db.commit()


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    return TestClient(app)


class Directory:
    """Builds synthetic people (never real directory rows) and makes API calls as one of them."""

    def __init__(self, db, client):
        self.db = db
        self.client = client
        self._n = 0

    def person(self, name: str, *, admin: bool = False, role: str = "member", email: str | None = None) -> Person:
        """Email defaults to the lowercased name (so use one-word names unless you pass an email)."""
        self._n += 1
        p = Person(
            slack_user_id=f"U{self._n:04d}",
            email=email or f"{name.lower()}@atimotors.com",
            name=name,
            role=role,
            is_admin=admin,
        )
        self.db.add(p)
        self.db.commit()
        return p

    def call(self, who: Person | None, method: str, path: str, **kwargs):
        headers = {"X-Dev-User-Email": who.email} if who else {}
        return self.client.request(method, f"/api{path}", headers=headers, **kwargs)


@pytest.fixture
def directory(db, client):
    return Directory(db, client)


@pytest.fixture
def admin(directory):
    return directory.person("Admin", admin=True)


def make_team(directory, admin, name: str, manager: Person) -> dict:
    res = directory.call(
        admin, "POST", "/teams",
        json={"name": name, "initial_manager_person_id": str(manager.id), "reason": "set up"},
    )
    assert res.status_code == 201, res.text
    return res.json()


@pytest.fixture
def npi(db, directory, admin):
    """Asha runs NPI, Ravi is a member, Zoe is on no team."""
    asha, ravi, zoe = directory.person("Asha"), directory.person("Ravi"), directory.person("Zoe")
    team = make_team(directory, admin, "NPI", asha)
    directory.call(asha, "POST", f"/teams/{team['id']}/members", json={"person_id": str(ravi.id)})
    db.expire_all()  # the API changed these people in its own session; reload them here
    return {"asha": asha, "ravi": ravi, "zoe": zoe, "team": team}
