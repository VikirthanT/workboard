"""The production stack must never reach the development sign-in, and must not run the API as root."""
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


def test_api_image_runs_as_a_non_root_user():
    dockerfile = (ROOT / "Dockerfile.api").read_text()
    assert re.search(r"^USER (?!root\b)\S+", dockerfile, re.M)


def test_the_production_image_does_not_install_test_tools():
    assert "pytest" not in (ROOT / "server" / "requirements.txt").read_text()
