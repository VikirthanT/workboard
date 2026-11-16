"""The production stack must never reach the development sign-in, must not run the API as root, and must send the
browser security headers."""
import base64
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _api_service() -> str:
    compose = (ROOT / "docker-compose.yml").read_text()
    return re.search(r"^  server:\n(.*?)(?=^  \w)", compose, re.S | re.M).group(1)


def test_production_compose_forces_dev_auth_off_and_passes_no_env_file():
    service = _api_service()
    assert 'DEV_AUTH: "false"' in service
    assert not re.search(r"^\s*env_file:", service, re.M)  # nothing dev-only in .env can reach the container


def test_production_api_is_hardened():
    service = _api_service()
    assert "cap_drop: [ALL]" in service
    assert "no-new-privileges:true" in service


def test_every_production_service_drops_all_capabilities_and_cannot_gain_privileges():
    compose = (ROOT / "docker-compose.yml").read_text()
    services = re.findall(r"^  ([\w-]+):\n(.*?)(?=^  \w|^volumes:)", compose, re.S | re.M)  # names can have a hyphen (directory-sync)
    assert {name for name, _ in services} == {"db", "server", "slack", "scheduler", "directory-sync", "frontend", "nginx"}  # a new service must be added here
    for name, body in services:
        assert "cap_drop: [ALL]" in body, f"{name} keeps Linux capabilities it does not need"
        assert "no-new-privileges:true" in body, f"{name} can gain privileges"
        added = re.search(r"cap_add: \[(.*?)\]", body)
        assert not added or set(added.group(1).replace(" ", "").split(",")) <= {
            "CHOWN", "SETUID", "SETGID", "NET_BIND_SERVICE", "DAC_OVERRIDE", "FOWNER",
        }, f"{name} adds a capability beyond what its image needs"
    assert "privileged" not in compose and "docker.sock" not in compose


def _service(name: str) -> str:
    compose = (ROOT / "docker-compose.yml").read_text()
    return re.search(rf"^  {name}:\n(.*?)(?=^  \w|^volumes:)", compose, re.S | re.M).group(1)


def test_make_prod_up_starts_the_weekly_people_sync_with_the_apis_image_the_schedule_and_the_bot_token_only():
    sync = _service("directory-sync")
    assert "image: workboard-server" in sync and 'command: ["python", "-m", "identity.directory_scheduler"]' in sync
    assert 'DEV_AUTH: "false"' in sync and not re.search(r"^\s*env_file:", sync, re.M)
    for setting in ("DIRECTORY_SYNC_SCHEDULE", "SLACK_BOT_TOKEN", "BOOTSTRAP_ADMIN_EMAILS"):
        assert f"{setting}: ${{{setting}:-}}" in sync, f"the people sync is not given {setting}"
    assert "SLACK_APP_TOKEN" not in sync  # it never listens to Slack, so it never sees the app token
    assert "LLM_" not in sync and "STANDUP_" not in sync  # nothing from the standup side


def test_make_prod_up_starts_the_standup_scheduler_with_the_apis_image_and_the_schedule_but_no_slack_tokens():
    scheduler = _service("scheduler")
    assert "image: workboard-server" in scheduler and 'command: ["python", "-m", "standups.scheduler"]' in scheduler
    assert 'DEV_AUTH: "false"' in scheduler and not re.search(r"^\s*env_file:", scheduler, re.M)
    for setting in ("STANDUP_SYNC_SCHEDULE", "STANDUP_DB_URL", "LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY"):
        assert f"{setting}: ${{{setting}:-}}" in scheduler, f"the scheduler is not given {setting}"
    assert "SLACK_" not in scheduler  # it never posts to Slack
    assert "/opt/standup-snapshot:ro" in scheduler  # the copy of the standup database, read only


def test_make_prod_up_starts_the_slack_listener_with_the_apis_image_and_its_own_tokens():
    slack, server = _service("slack"), _service("server")
    assert "image: workboard-server" in slack and 'command: ["python", "-m", "slack.listener"]' in slack
    assert 'DEV_AUTH: "false"' in slack and not re.search(r"^\s*env_file:", slack, re.M)
    assert "SLACK_BOT_TOKEN" in slack and "SLACK_APP_TOKEN" in slack
    assert "SLACK_APP_TOKEN" not in server  # the API never sees the app token
    assert "service_healthy" in slack  # waits for the migrations
    assert "ports:" not in slack  # Socket Mode dials out; nothing connects in
    # `make prod-up` starts every service in the compose file, so the listener comes up with it.
    assert re.search(r"^prod-up: .*\n\tdocker compose up -d --build --wait", (ROOT / "Makefile").read_text(), re.M)


def test_the_standup_database_copy_is_mounted_read_only_and_the_new_settings_reach_the_api():
    server = _service("server")
    # The host folder comes from STANDUP_DB_DIR; the path inside is fixed so STANDUP_DB_URL is the same everywhere.
    assert re.search(r"- \$\{STANDUP_DB_DIR:-\./standup-snapshot\}:/opt/standup-snapshot:ro", server)
    assert "/opt/standup-bot" not in (ROOT / "docker-compose.yml").read_text()  # the live standup folder (with its .env) is never mounted
    for name in ("STANDUP_DB_URL", "LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY", "LLM_BASE_URL", "SLACK_BOT_TOKEN"):
        assert re.search(rf"^\s+{name}: \$\{{{name}:-\}}", server, re.M), f"{name} does not reach the API container"


def test_api_image_runs_as_a_non_root_user():
    dockerfile = (ROOT / "Dockerfile.api").read_text()
    assert re.search(r"^USER (?!root\b)\S+", dockerfile, re.M)


def test_the_production_image_does_not_install_test_tools():
    assert "pytest" not in (ROOT / "server" / "requirements.txt").read_text()


def _nginx_header(name: str) -> str:
    conf = (ROOT / "nginx" / "nginx.conf").read_text()
    match = re.search(rf'^\s*add_header {name} (?:"([^"]*)"|(\S+)) always;', conf, re.M)
    assert match, f"nginx.conf does not send {name} on every response (with `always`)"
    return match.group(1) or match.group(2)


def test_nginx_sends_the_security_headers_on_every_response():
    assert "max-age=" in _nginx_header("Strict-Transport-Security")
    assert "camera=()" in _nginx_header("Permissions-Policy")
    for name in ("X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy"):
        assert _nginx_header(name)


def _nginx_conf() -> str:
    return (ROOT / "nginx" / "nginx.conf").read_text()


def test_nginx_blanks_the_dev_sign_in_header_on_every_api_location():
    conf = _nginx_conf()
    api_locations = re.findall(r"location (?:/api/(?:tasks/import)?|/api/tasks/import) \{(.*?)\n    \}", conf, re.S)
    assert len(api_locations) == 2  # /api/ and the upload route; a new proxied location must be added to this check
    for body in api_locations:
        assert 'proxy_set_header X-Dev-User-Email "";' in body


def test_nginx_hides_the_dev_account_list_and_the_api_docs_pages():
    conf = _nginx_conf()
    assert re.search(r"location /api/dev/ \{\s*return 404;\s*\}", conf)
    assert re.search(r"location ~ \^/\(docs\|redoc\|openapi\\\.json\)\$ \{\s*return 404;\s*\}", conf)


def test_nginx_limits_request_bodies_and_logs_no_query_strings():
    conf = _nginx_conf()
    assert re.search(r"^    client_max_body_size 1m;", conf, re.M)  # the default for every route
    assert re.search(r"location /api/tasks/import \{\s*client_max_body_size 3m;", conf)  # the 2 MB upload plus overhead
    # the one-time sign-in code is in a query string, so the access log must record the path only
    assert "$uri" in re.search(r"log_format workboard (.*?);", conf, re.S).group(1)
    assert "$request " not in conf and "$request_uri" not in conf and "$args" not in conf
    assert "access_log /var/log/nginx/access.log workboard;" in conf


def test_nginx_rate_limits_every_api_call_and_the_sign_in_endpoints_harder():
    conf = _nginx_conf()
    assert re.search(r"limit_req_zone \$binary_remote_addr zone=wb_api:\S+ rate=\d+r/m;", conf)
    assert re.search(r"limit_req_zone \$wb_auth_key zone=wb_auth:\S+ rate=\d+r/m;", conf)
    assert re.search(r"map \$uri \$wb_auth_key \{\s*~\^/api/auth/\s+\$binary_remote_addr;\s*default\s+\"\";", conf)
    assert "limit_req_status 429;" in conf
    # both proxied API locations are inside the general limit; the main one is also inside the sign-in limit
    api = re.search(r"location /api/ \{(.*?)\n    \}", conf, re.S).group(1)
    upload = re.search(r"location /api/tasks/import \{(.*?)\n    \}", conf, re.S).group(1)
    assert "limit_req zone=wb_api" in api and "limit_req zone=wb_auth" in api
    assert "limit_req zone=wb_api" in upload


def test_nginx_takes_the_visitor_address_only_from_private_proxies_and_the_last_untrusted_entry():
    conf = _nginx_conf()
    trusted = re.findall(r"set_real_ip_from (\S+);", conf)
    assert trusted and all(re.match(r"(10\.|172\.16\.|192\.168\.|127\.)", cidr) for cidr in trusted)  # never a public range
    assert "real_ip_header X-Forwarded-For;" in conf
    assert "real_ip_recursive on;" in conf  # without it a visitor could put any address first in the header


def test_the_content_security_policy_is_strict_and_allows_the_one_inline_script():
    policy = _nginx_header("Content-Security-Policy")
    directives = dict(d.strip().split(" ", 1) for d in policy.split(";") if d.strip())
    assert directives["default-src"] == "'self'"
    assert directives["object-src"] == "'none'" and directives["frame-ancestors"] == "'none'"
    assert "'unsafe-inline'" not in directives["script-src"] and "'unsafe-eval'" not in directives["script-src"]
    assert not re.search(r"https?:|\*", policy)  # nothing is allowed from anywhere else

    # The theme script in index.html is inline, so its hash must be in the policy; editing the script changes the hash.
    html = (ROOT / "client" / "index.html").read_text()
    inline = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
    assert len(inline) == 1, "index.html has an inline script the policy does not know about"
    digest = base64.b64encode(hashlib.sha256(inline[0].encode()).digest()).decode()
    assert f"'sha256-{digest}'" in directives["script-src"], f"update the script hash in nginx.conf to sha256-{digest}"
