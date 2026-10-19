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

# The people directory loaded into the database (dev and prod): PEOPLE_FILE from .env, default seed/people.json.
# It can be a file, or a folder that holds people.json. Put it after LOAD_DOTENV; it sets $$f.
# Missing is fine: the load is skipped with a note.
PEOPLE_PATH = f="$${PEOPLE_FILE:-seed/people.json}"; [ ! -d "$$f" ] || f="$$f/people.json";
NO_PEOPLE = echo "NOTE: $$f not found, so no people were loaded. Set PEOPLE_FILE in .env (see .env.example), or make the file with seed/csv_to_people.py."

.PHONY: help install dev web-dev db-logs dev-down build typecheck test client-test clean \
        server-install db-up db-down db-migrate db-seed db-demo db-demo-reset db-demo-remove api-dev server-test \
        prod-up prod-load-people prod-down prod-logs

help:
	@echo "make install    install frontend dependencies"
	@echo ""
	@echo "Development (loads .env):"
	@echo "make dev        database + migrations + people + demo accounts + API on :8000 (DEV_AUTH=true) + Vite on :5173, with the API, database and Vite logs in one terminal"
	@echo "make db-logs    follow the dev database's log on its own"
	@echo "make dev-down  stop the dev database (data kept)"
	@echo "make server-install  create server/.venv and install the server dependencies"
	@echo "make db-up           start only the dev Postgres container (127.0.0.1:5436)"
	@echo "make db-migrate      apply the Alembic migrations"
	@echo "make db-seed         load PEOPLE_FILE (default seed/people.json) + bootstrap admins into the database (skipped with a note if missing)"
	@echo "make db-demo         load the demo world: Admin, Manager 1, Manager 2, two teams, 14 tasks (dev only)"
	@echo "make db-demo-reset   remove the demo data and load it again"
	@echo "make db-demo-remove  remove the demo data only (make dev-down keeps it; docker compose -f docker-compose.dev.yml down -v wipes the whole dev database)"
	@echo "make api-dev         run the API on :8000 with the dev sign-in stub (DEV_AUTH=true, local only)"
	@echo "make server-test     run only the server tests (own test database)"
	@echo ""
	@echo "Production (docker-compose.yml: database + API; no seeds, no dev sign-in):"
	@echo "make prod-up    build and start the stack (migrations run on start), then load PEOPLE_FILE if it exists"
	@echo "make prod-load-people  just the people load, against the running prod stack"
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
dev: server/.venv/bin/uvicorn db-up db-migrate db-seed db-demo
	$(MAKE) -j3 api-dev web-dev db-logs

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
	server/.venv/bin/pip install -r server/requirements.txt

db-up:
	$(DEV_COMPOSE) up -d --wait db

db-down: dev-down

db-migrate:
	@$(LOAD_ENV) cd server && .venv/bin/alembic upgrade head

db-seed:
	@$(LOAD_ENV) $(PEOPLE_PATH) if [ -f "$$f" ]; then server/.venv/bin/python seed/load_db.py "$$f"; else $(NO_PEOPLE); fi

# Development only: Admin, Manager 1 and Manager 2 with two teams and 14 tasks, so the login list has accounts to pick.
# Skips if already loaded; `make db-demo-reset` loads it again. Never part of the production stack.
db-demo:
	@$(LOAD_ENV) DEV_AUTH=true server/.venv/bin/python seed/demo_db.py

db-demo-reset:
	@$(LOAD_ENV) DEV_AUTH=true server/.venv/bin/python seed/demo_db.py --reset

db-demo-remove:
	@$(LOAD_ENV) DEV_AUTH=true server/.venv/bin/python seed/demo_db.py --remove

# DEV_AUTH=true is for local development only; without it the API answers 501 until Google sign-in exists.
api-dev:
	@$(LOAD_ENV) cd server && DEV_AUTH=true .venv/bin/uvicorn main:app --reload --port 8000

server-test:
	@$(LOAD_ENV) python3 scripts/test_all.py server

# Production: no DEV_AUTH and no mock reach the containers (see docker-compose.yml).
prod-up:
	docker compose up -d --build --wait
	@$(MAKE) --no-print-directory prod-load-people

# One-off container: the loader and the people file are mounted read-only for this run, never baked into the image.
prod-load-people:
	@$(LOAD_ENV) $(PEOPLE_PATH) if [ -f "$$f" ]; then \
		docker compose run --rm -T -e BOOTSTRAP_ADMIN_EMAILS \
			-v "$(abspath seed/load_db.py):/app/load_db.py:ro" \
			-v "$$(realpath "$$f"):/data/people.json:ro" \
			server python load_db.py /data/people.json; \
	else $(NO_PEOPLE); fi

prod-down:
	docker compose down

prod-logs:
	docker compose logs -f

clean:
	rm -rf client/dist
