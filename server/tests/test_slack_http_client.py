"""The one shared HTTP client behind every Slack call: it keeps the connection open, and holds nothing that could leak.
A fake transport stands in for the network, so no test reaches Slack."""
import httpx
import pytest

from slack import client

REAL_POST = client._post  # the tests' autouse guard replaces it with a refusal; these tests want the real one


@pytest.fixture
def seen(monkeypatch):
    """Swap the shared client for one on a fake transport; returns the requests it was asked to make."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/files.getUploadURLExternal"):
            return httpx.Response(200, json={"ok": True, "upload_url": "https://files.example/upload", "file_id": "F1"})
        if request.url.host == "files.example":
            return httpx.Response(200, text="OK")
        return httpx.Response(200, json={"ok": True, "channel": {"id": "D1"}}, headers={"Set-Cookie": "session=abc; Path=/"})

    monkeypatch.setattr(client, "_post", REAL_POST)
    monkeypatch.setattr(client, "_shared", client._new_client(transport=httpx.MockTransport(handler)))
    return requests


def test_there_is_one_shared_client_and_it_carries_no_default_headers_and_follows_no_redirects():
    first = client._http()

    assert client._http() is first
    assert "authorization" not in {k.lower() for k in first.headers}
    assert first.follow_redirects is False


def test_cookies_slack_sets_are_never_sent_back(seen):
    client.open_dm("xoxb-secret", "U1")
    client.open_dm("xoxb-secret", "U1")

    assert len(seen) == 2 and all("cookie" not in request.headers for request in seen)


def test_the_token_goes_to_slacks_api_but_not_to_the_upload_address_slack_hands_back(seen):
    client.post_with_pdf("xoxb-secret", "C1", "text", "Task.pdf", b"%PDF")

    by_host = {request.url.host: request for request in seen}
    assert by_host["slack.com"].headers["authorization"] == "Bearer xoxb-secret"
    assert "authorization" not in by_host["files.example"].headers


def test_a_network_failure_is_a_slack_error_without_the_token(monkeypatch):
    def fail(request):
        raise httpx.ConnectError("no route", request=request)

    monkeypatch.setattr(client, "_post", REAL_POST)
    monkeypatch.setattr(client, "_shared", client._new_client(transport=httpx.MockTransport(fail)))

    with pytest.raises(client.SlackError) as err:
        client.open_dm("xoxb-secret", "U1")

    assert "xoxb-secret" not in str(err.value) and "could not be reached" in str(err.value)
