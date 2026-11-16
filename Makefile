# Work Board: a React frontend (client/) on a FastAPI + Postgres backend (server/).
# Run from the repo root. Settings live in .env (copy .env.example): Docker targets get them from docker compose,
# host targets (migrate, people load, api-dev, tests) load .env through LOAD_ENV below. The server itself reads only
# environment variables, never the file.

# Host targets: load .env the way a shell does (quote values that contain spaces or # & $).
LOAD_DOTENV = set -a; [ ! -f .env ] || . ./.env; set +a;

# The database targets also build DATABASE_URL from the POSTGRES_* parts unless .env sets one.
# Nothing is printed; the password has no default.
LOAD_ENV = $(LOAD_DOTENV) \
	export DATABASE_URL="$${DATABASE_URL:-postgresql+psycopg://$${POSTGRES_USER:-workboard}:$${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is not set, see .env.example}@127.0.0.1:$${POSTGRES_PORT:-5436}/$${POSTGRES_DB:-workboard}}";

DEV_COMPOSE = docker compose -f docker-compose.dev.yml

.PHONY: help install dev web-dev db-logs dev-down build typecheck test client-test clean \
        server-install db-up db-down db-migrate db-sync-people db-demo db-demo-standup db-demo-reset db-demo-remove api-dev slack-dev scheduler-dev server-test server-cov e2e \
        prod-up prod-backup prod-sync-people prod-standup-snapshot prod-down prod-logs

help:
	@echo "make install    install frontend dependencies"
	@echo ""
	@echo "Development (loads .env):"
	@echo "make dev        database + migrations + demo accounts + API on :8000 (DEV_AUTH=true) + Vite on :5173, with the API, database and Vite logs in one terminal"
	@echo "make db-logs    follow the dev database's log on its own"
	@echo "make dev-down  stop the dev database (data kept)"
	@echo "make server-install  create server/.venv and install the server dependencies"
	@echo "make db-up           start only the dev Postgres container (127.0.0.1:5436)"
	@echo "make db-migrate      apply the Alembic migrations"
	@echo "make db-sync-people  load the people from the Slack workspace now (needs SLACK_BOT_TOKEN) and make the BOOTSTRAP_ADMIN_EMAILS admins; every run is audited"
	@echo "make db-demo         load the demo world: Admin, Manager 1, Manager 2, two teams, 14 tasks (dev only)"
	@echo "make db-demo-standup write a made-up standup database for a team in the dev database (default NPI) to try Suggestions"
	@echo "make db-demo-reset   remove the demo data and load it again"
	@echo "make db-demo-remove  remove the demo data only (make dev-down keeps it; docker compose -f docker-compose.dev.yml down -v wipes the whole dev database)"
	@echo "make api-dev         run the API on :8000 with the dev sign-in stub (DEV_AUTH=true, local only)"
	@echo "make server-test     run only the server tests (own test database)"
	@echo "make server-cov      the server tests plus a coverage table with the uncovered lines"
	@echo "make e2e             Playwright smoke tests in a browser, on a throwaway database with the demo world (not part of make test)"
	@echo ""
	@echo "Production (docker-compose.yml: database + API; no seeds, no dev sign-in):"
	@echo "make prod-up    build and start the stack (database, API, Slack listener, standup scheduler, weekly people sync, frontend, nginx; migrations run on start), then sync the people from Slack once"
	@echo "make slack-dev  run the Slack listener (DM buttons) beside make api-dev; make dev starts it too"
	@echo "make prod-sync-people  just the people sync from Slack, once, against the running prod stack"
	@echo "make prod-standup-snapshot  copy the standup app's database to standup-snapshot/ (the API reads that copy); run once before the first prod-up, then from cron"
	@echo "make prod-down  stop it (data kept)"
	@echo "make prod-logs  follow the logs"
	@echo ""
	@echo "Frontend:"
	@echo "make build      typecheck + production build"
	@echo "make typecheck  tsc --noEmit"
	@echo "make test       run ALL tests: the frontend's, then the server's (starts the dev database if needed)"
	@echo "make client-test  run only the frontend's unit tests"
	@echo "make clean      remove the frontend build output"

install:
	cd client && npm install

# The whole local stack: database, migrations, people, the API (dev sign-in on) and the Vite dev server, with the
# API's, the database's and Vite's logs together in this terminal. Ctrl-C stops the servers and the log tail
# (the database container keeps running; `make dev-down` stops it).
dev: server/.venv/bin/uvicorn db-up db-migrate db-demo
	$(MAKE) -j4 api-dev web-dev db-logs slack-dev

# Follows the dev database's log, starting from its last few lines.
db-logs:
	$(DEV_COMPOSE) logs -f --tail=10 db

web-dev:
	cd client && npm run dev -- --host

# Builds server/.venv the first time only.
server/.venv/bin/uvicorn:
	$(MAKE) server-install

dev-down:
	$(DEV_COMPOSE) down

build:
	cd client && npm run build

typecheck:
	cd client && npm run typecheck

# Every test: the frontend's unit tests, then the server's. The server tests need the dev database and the venv,
# so they are set up first; they use their own database (workboard_test_<pid>), never your dev data.
test: server/.venv/bin/uvicorn db-up
	@$(LOAD_ENV) python3 scripts/test_all.py

# Same output as `make test`, one suite at a time: every test by name with PASSED / FAILED and its percentage,
# then a table with the percentage that passed.
client-test:
	@python3 scripts/test_all.py frontend

server-install:
	python3 -m venv server/.venv
	server/.venv/bin/pip install -r server/requirements-dev.txt

db-up:
	$(DEV_COMPOSE) up -d --wait db

db-down: dev-down

db-migrate:
	@$(LOAD_ENV) cd server && .venv/bin/alembic upgrade head

# The people directory comes from the Slack workspace (users.list), not from a file. Needs SLACK_BOT_TOKEN in .env with the
# users:read and users:read.email scopes; without it this says so and does nothing. Not part of make dev, which has its own
# demo accounts: run it when you want the real directory in the dev database. `make db-sync-people ARGS=--allow-large-removal`.
db-sync-people:
	@$(LOAD_ENV) cd server && TZ=Asia/Kolkata .venv/bin/python -m identity.directory_scheduler --once $(ARGS)

# Development only: Admin, Manager 1 and Manager 2 with two teams and 14 tasks, so the login list has accounts to pick.
# Skips if already loaded; `make db-demo-reset` loads it again. Never part of the production stack.
db-demo:
	@$(LOAD_ENV) DEV_AUTH=true server/.venv/bin/python seed/demo_db.py

# A made-up standup database for a team already in the dev database (default NPI), to try Suggestions end to end.
# `make db-demo-standup ARGS="--team Validation"` for another team. Prints the STANDUP_DB_URL line for your .env.
db-demo-standup:
	@$(LOAD_ENV) DEV_AUTH=true server/.venv/bin/python seed/demo_standup_db.py $(ARGS)

db-demo-reset:
	@$(LOAD_ENV) DEV_AUTH=true server/.venv/bin/python seed/demo_db.py --reset

db-demo-remove:
	@$(LOAD_ENV) DEV_AUTH=true server/.venv/bin/python seed/demo_db.py --remove

# DEV_AUTH=true is for local development only; without it the API answers 501 until Google sign-in exists.
# The Slack listener: receives the DM button presses over Socket Mode. Needs SLACK_BOT_TOKEN and SLACK_APP_TOKEN in .env;
# without them it prints a note and exits, so `make dev` carries on without it. Restart it to pick up code changes.
slack-dev:
	@$(LOAD_ENV) cd server && TZ=Asia/Kolkata DEV_AUTH=true .venv/bin/python -m slack.listener

# The standup scheduler: reads the standups at the times in STANDUP_SYNC_SCHEDULE (India time). Idles when it is empty.
scheduler-dev:
	@$(LOAD_ENV) cd server && TZ=Asia/Kolkata DEV_AUTH=true .venv/bin/python -m standups.scheduler

# `make api-dev API_PORT=8001` runs a second API beside the one on :8000 (for example to try new .env settings without stopping it).
API_PORT ?= 8000
api-dev:
	@$(LOAD_ENV) cd server && TZ=Asia/Kolkata DEV_AUTH=true .venv/bin/uvicorn main:app --reload --port $(API_PORT)

server-test:
	@$(LOAD_ENV) python3 scripts/test_all.py server

# Playwright smoke tests: the real API and Vite on ports 8100 / 5174, on a throwaway database with the demo world
# (dropped afterwards). Needs the dev database up and a browser: cd client && npx playwright install chromium (once).
e2e: server/.venv/bin/uvicorn db-up
	@$(LOAD_ENV) python3 scripts/test_all.py e2e

# Server tests with a coverage table of the app code and the lines no test reaches (settings: server/.coveragerc).
server-cov:
	@$(LOAD_ENV) cd server && .venv/bin/pytest -q --cov --cov-report=term-missing

# Production: no DEV_AUTH and no mock reach the containers (see docker-compose.yml).
prod-up: prod-backup
	docker compose up -d --build --wait
	@$(MAKE) --no-print-directory prod-sync-people || echo "NOTE: the people sync did not run (see above); the stack is up. Run make prod-sync-people once Slack is set up."

# Dump the running database to backups/ (private, gitignored) before anything is changed; keeps the newest 14.
# On a first deploy there is no database yet, so it says so and skips. A failed dump stops prod-up.
prod-backup:
	@if [ -z "$$(docker compose ps --status running -q db)" ]; then \
		echo "NOTE: database is not running, so there is nothing to back up (first deploy?)."; \
	else \
		umask 077; mkdir -p backups; f="backups/workboard-$$(date +%F-%H%M%S).sql.gz"; \
		docker compose exec -T db sh -c 'pg_dump -U "$$POSTGRES_USER" "$$POSTGRES_DB"' > "$$f.tmp" \
			&& gzip "$$f.tmp" && mv "$$f.tmp.gz" "$$f" || { rm -f "$$f.tmp" "$$f.tmp.gz"; echo "Backup failed, nothing was changed."; exit 1; }; \
		echo "Backup written to $$f"; \
		ls -1t backups/workboard-*.sql.gz | tail -n +15 | xargs -r rm -f; \
	fi

# One-off container from the API's own image: reads the Slack workspace once and loads the people, then makes the
# BOOTSTRAP_ADMIN_EMAILS admins (how the first admin gets in). Safe to run again; `ARGS=--allow-large-removal` allows a run
# that deactivates many people. Without SLACK_BOT_TOKEN it says so and does nothing.
prod-sync-people:
	@$(LOAD_ENV) docker compose run --rm -T -e BOOTSTRAP_ADMIN_EMAILS server python -m identity.directory_scheduler --once $(ARGS)

# The standup app keeps its database in WAL mode, which the API container cannot open from a read only mount. This copies
# it to a plain file in STANDUP_SNAPSHOT_DIR, which the API mounts instead (scripts/standup_snapshot.py; the live file is
# only read). Run it as the user that owns the standup database, once before the first prod-up and then from cron.
# Other places: `make prod-standup-snapshot STANDUP_SOURCE=/path/standup.db STANDUP_SNAPSHOT_DIR=/path/folder` (this
# target does not read .env; if STANDUP_DB_DIR is changed there, change STANDUP_SNAPSHOT_DIR to match).
STANDUP_SOURCE ?= /opt/standup-bot/standup.db
STANDUP_SNAPSHOT_DIR ?= standup-snapshot
prod-standup-snapshot:
	@python3 scripts/standup_snapshot.py $(STANDUP_SOURCE) $(STANDUP_SNAPSHOT_DIR)

prod-down:
	docker compose down

prod-logs:
	docker compose logs -f

clean:
	rm -rf client/dist
