#!/usr/bin/env python3
"""Create or drop the throwaway database the end-to-end tests run against. Used by scripts/test_all.py (make e2e).

    server/.venv/bin/python scripts/e2e_db.py create    prints the new DATABASE_URL (it holds the password: capture it, do not log it)
    server/.venv/bin/python scripts/e2e_db.py drop

The name is workboard_e2e_<pid of the parent run>; DATABASE_URL (from .env through make) names the server and the
login. The development database is never touched.
"""
import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

base = make_url(os.environ["DATABASE_URL"])
name = f"workboard_e2e_{os.environ['WB_E2E_RUN']}"
admin = create_engine(base, isolation_level="AUTOCOMMIT")

with admin.connect() as conn:
    conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
    if sys.argv[1] == "create":
        conn.execute(text(f"CREATE DATABASE {name}"))
        print(base.set(database=name).render_as_string(hide_password=False))
