# Deployment: what runs where, and why

This explains the production containers from scratch, then the plan for the two we have not built yet. Status:
the database and API containers exist (`docker-compose.yml`, `make prod-up`); the nginx and frontend container is
planned and will be built when it is needed. HTTPS is the last step, after a domain exists; plain HTTP is fine until then.

## First, what is a container?

A container is a small, sealed box that holds one program and everything that program needs to run (its libraries,
its settings). You start it with one command and it behaves the same on your laptop and on a server. `docker compose`
starts several boxes together and connects them with a private network, so the boxes can talk to each other by name
(for example the API reaches the database at `db:5432`) while the outside world sees only what we choose to publish.

## The three boxes in production

```
 browser ──► [ nginx ] ──► /api/...  ──► [ API ] ──► [ database ]
              port 80                      FastAPI      Postgres
              serves the web page          (Python)     (stores everything)
```

Only nginx has a door to the outside (port 80). The API and the database have no published ports, so nobody can
reach them directly from outside the machine.

### 1. Database (built, `db`)
Postgres, from the official image. It stores people, teams, tasks, timelines and the audit log. Its data lives in a
named volume, so removing and recreating the container does not lose it.

### 2. API (built, `server`)
Our Python (FastAPI) program, built from `Dockerfile.api`: start from a small Python image, install the packages in
`server/requirements.txt`, copy `server/` in. When it starts it first applies the database migrations, then serves.
It answers every `/api/...` request: who you are, the board, tasks, reports.

**What time is it?** The image is set to Indian time (`TZ=Asia/Kolkata`, with `tzdata` installed so the setting
works). "Today" for due dates, overdue flags, the Done-on date and the reports comes from this clock, not from the
user's browser, so the day changes at midnight in India. The database stores moments with their zone, so nothing
stored changes.

**How many workers?** A worker is one running copy of the API process. We start **2** (`uvicorn --workers 2` in
`Dockerfile.api`): if one is busy or crashes the other still answers, and two requests can be handled at the same
moment. For about eight managers one would do; two is the safe, cheap default. Raise it only if the API is ever
slow under load. (In development `make api-dev` runs one worker with auto-reload.) The migrations run once, before
the workers start, so they never race each other.

### 3. nginx with the frontend (planned, `nginx`)
This is the one that needs explaining, because "the frontend container" and "the nginx container" turn out to be
the **same** container.

**What the frontend is.** The screens (React code) are written in many source files that a browser cannot run
as they are. `npm run build` compiles them into a handful of plain files: one `index.html`, some `.js` and `.css`
files, fonts and images (the `dist/` folder). That is the whole frontend. It is just files. After it is built there
is nothing to "run": any web server can hand those files to a browser, and the browser runs them.

**What nginx is.** A web server: a small, very fast, very well-tested program whose job is to receive requests and
answer them, either by sending a file or by passing the request on to another program. We use it for two jobs:

1. **Hand out the frontend files.** A request for `/` or `/boards` gets `index.html` (the React app takes over from
   there, which is why any unknown path must also return `index.html`: otherwise reloading the page on `/boards`
   would give "not found"). Request for a `.js`, `.css` or image gets that file, with caching so it is downloaded once.
2. **Pass `/api/...` on to the API container.** The browser only ever talks to one address. Page and API share
   that address, so there are no cross-origin problems and the frontend can simply call `/api/...`.

**How the container is built** (`Dockerfile.nginx`, two stages, the same idea MDM uses):
- Stage 1, a throwaway Node image: copy `client/`, `npm ci`, `npm run build`. This produces `dist/`.
- Stage 2, the image we keep: plain `nginx`, with only `dist/` copied in, plus our `nginx.conf`.
Node and the source code are left behind in stage 1, so the final image is small and holds nothing but the built files
and the web server.

**What is in it:** the built frontend (`/usr/share/nginx/html`) and one config file saying "serve those files; send
`/api/` to `server:8000`; add security headers; compress; cache assets".

**Why we need it at all:**
- Without it nothing serves the web page in production. The API only speaks JSON.
- It is the single public door, so the API and database can stay private.
- It does the dull work properly (compression, caching, slow connections, headers) which Python should not.
- It is where HTTPS will plug in later, with no change to the API or the frontend.
- The same shape as MDM, so what you learn there applies here.

(There is a smaller alternative: let the API container also hand out the built files, so there is no nginx. It would
work for eight users, but we would have to move to nginx later for HTTPS and headers anyway, so we go straight to it.)

### And in development?
`make dev` does not use these containers: the API and Vite (the frontend's live-reloading dev server) run on your
machine, and Vite passes `/api` to the API, which is the small job nginx does in production. Only the database is a
container. That keeps the edit-and-see loop fast.

## The plan (do when needed; HTTP only)

1. **`Dockerfile.nginx`**: the two stages above.
2. **`nginx/nginx.conf`** (HTTP, port 80): serve `dist/` with the `index.html` fallback; `location /api/` proxies to
   `server:8000` with the usual forwarded headers; gzip; one-year cache on built assets; `server_tokens off`;
   the security headers that need no HTTPS (the strict ones, HSTS and a tight CSP, wait for HTTPS).
3. **`docker-compose.yml`**: add an `nginx` service (builds `Dockerfile.nginx`, publishes port 80, starts after the
   API is healthy). The API and database stay unpublished.
4. **`.dockerignore`** allow-list gains `client/` (without `node_modules`, `dist`) for the build.
5. **Test it here over plain HTTP:** `make prod-up`; `GET /` returns the page; `GET /api/health` answers through
   nginx; reloading `/boards` returns the page, not a 404; the login page renders in a browser.
6. **Docs:** this file, `CLAUDE.md`, `server/README.md`.

### Two things to know before then
- **Containers alone do not make production usable.** Real sign-in is Google, which is built last, and the
  development sign-in list is turned off in production on purpose. Until Google sign-in exists, the production page
  loads but nobody can sign in.
- **Google needs HTTPS.** Google only accepts a plain-HTTP redirect address for `localhost`. For a real address it
  must be HTTPS, which needs a domain and a certificate. So HTTP is fine for building and testing the containers,
  but it is a stopgap: HTTPS is not optional once Google sign-in goes in.

## Google sign-in: what it needs

**Status: the server side is built** (`server/auth/`, see its README, 70 tests with Google faked). What is left is
yours: create the OAuth client (part 1 below) and put the five settings in `.env` (part 3), then try it with
"Sign in with real Google" at the bottom of the development account list. Environment variables on their own were never
enough (the code had to exist), which is why this was a build, not a setting. The three parts, for the record:

**1. Set-up in Google (you, once; no code).** In Google Cloud Console, create an OAuth client of type "Web
application" and a consent screen set to **Internal** (so only `@atimotors.com` accounts can sign in at all). Add the
**authorised redirect address** of the API's callback. Google accepts plain `http://localhost:8000/...` for
development, so real Google sign-in can be tried locally with no domain. For production the address must be
**https**, which needs the domain and certificate. Google then gives you a client ID and a client secret.

**2. Server code (built).** A new feature on the server:
- `GET /api/auth/google`: send the browser to Google, with a random `state` to stop forged callbacks.
- `GET /api/auth/google/callback`: Google comes back here with a code; the server swaps it for the person's
  verified email, checks it ends `@atimotors.com`, and checks the person is an active manager or admin
  (otherwise `/login?error=not_onboarded` or `domain_not_allowed`, the messages the login page already shows).
- `GET /api/auth/google/exchange?code=`: trade our own one-time code for a session token.
- Session tokens: signed and expiring, accepted by `get_current_person` as `Authorization: Bearer <token>`
  (the browser already sends it in a production build), next to the dev header, which stays dev-only.
- One new package to verify Google's signatures, and tests for every refusal.

**3. Settings (you fill in `.env`).** Listed in `.env.example` under "Google sign-in" and passed to the API container
in `docker-compose.yml` (the prod stack passes the API only what it names): `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` (`http://localhost:5173/api/auth/google/callback` while developing),
`SECRET_KEY` (signs the tokens; generate with `openssl rand -hex 32`) and `TOKEN_TTL_SECONDS` (session length,
default 28800 = 8 hours). There is no `FRONTEND_URL`: the callback is reached through the frontend's own address, so
the redirects are relative. Until all of them are set, "Sign in with real Google" returns to the login page with
"Google sign-in is not configured on this server", and nothing else is affected.

The frontend is ready: the login page reads `/login?code=` and `/login?error=`, trades the code, and the session's
token is sent as `Authorization: Bearer` on every call.

## Later: HTTPS (when there is a domain)
Add the certificate step (certbot / Let's Encrypt, as in MDM): port 443, a redirect from 80, `SERVER_DOMAIN` in
`.env`, HSTS and a strict content-security policy. Only the nginx config and compose file change.
