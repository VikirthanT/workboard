"""The Slack Web API, the little of it we use: post a message with a PDF to a channel.

Plain HTTPS through httpx, no SDK. The one place that touches the network (`_post`), so tests replace it. A Slack error
carries only Slack's own error code (`channel_not_found`, `not_in_channel`, ...); the token is never put in a message.
"""
import http.cookiejar
import threading

import httpx

API = "https://slack.com/api"
TIMEOUT_SECONDS = 30.0


class SlackError(Exception):
    """Slack refused or could not be reached. The text is safe to store and show: it holds no token."""


def _new_client(**kwargs) -> httpx.Client:
    """The one HTTP client for every Slack call, so the secure connection is kept open between calls instead of being set up
    again each time. It holds nothing that could leak: no default headers (the token goes on each API call only, so it never
    reaches the file-upload address Slack hands back), no cookies (all refused), no redirects followed, certificates checked."""
    client = httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False, **kwargs)
    client.cookies.jar.set_policy(http.cookiejar.DefaultCookiePolicy(allowed_domains=[]))  # accept cookies from no domain
    return client


_shared: httpx.Client | None = None
_shared_lock = threading.Lock()


def _http() -> httpx.Client:
    global _shared
    with _shared_lock:  # the listener runs its handlers in threads
        if _shared is None:
            _shared = _new_client()
        return _shared


def _post(url: str, **kwargs) -> httpx.Response:
    try:
        return _http().post(url, **kwargs)
    except httpx.HTTPError as err:
        raise SlackError("Slack could not be reached.") from err


def _call(token: str, method: str, *, data: dict | None = None, json: dict | None = None) -> dict:
    res = _post(f"{API}/{method}", headers={"Authorization": f"Bearer {token}"}, data=data, json=json)
    if res.status_code != 200:
        raise SlackError(f"Slack answered HTTP {res.status_code}.")
    body = res.json()
    if not body.get("ok"):
        # For a rejected message Slack says which part is wrong in response_metadata.messages: keep it, it is what makes the
        # error fixable. It is Slack's own text about our request, never a token.
        detail = "; ".join(str(m) for m in (body.get("response_metadata") or {}).get("messages", [])[:3])
        raise SlackError(f"Slack refused it: {body.get('error', 'unknown_error')}." + (f" ({detail[:300]})" if detail else ""))
    return body


def open_dm(token: str, slack_user_id: str) -> str:
    """The id of the DM channel between the bot and this person (opened if it was not)."""
    return _call(token, "conversations.open", json={"users": slack_user_id})["channel"]["id"]


def _content(text: str, blocks: list[dict], color: str | None) -> dict:
    """The message body. With a `color` the blocks go inside an attachment, which is the only way Slack draws a coloured bar
    down the side of a message. Slack shows a top-level `text` above an attachment, which would only repeat what the card
    says, so here `text` goes in the attachment's `fallback` instead: still what a notification shows, not shown in the
    message. Without a colour the blocks are plain and `text` is their notification text."""
    if color:
        return {"attachments": [{"color": color, "blocks": blocks, "fallback": text}]}
    return {"text": text, "blocks": blocks}


def post_message(
    token: str, channel: str, text: str, blocks: list[dict], thread_ts: str | None = None, color: str | None = None
) -> str:
    """Post a message and return its `ts`, which is both its id and, for a card, the thread its replies go under.
    `text` is what a notification shows; `blocks` is the card."""
    body: dict = {"channel": channel, **_content(text, blocks, color)}
    if thread_ts:
        body["thread_ts"] = thread_ts
    return _call(token, "chat.postMessage", json=body)["ts"]


def update_message(token: str, channel: str, ts: str, text: str, blocks: list[dict], color: str | None = None) -> None:
    _call(token, "chat.update", json={"channel": channel, "ts": ts, **_content(text, blocks, color)})


def publish_home(token: str, slack_user_id: str, view: dict) -> None:
    """Replace what this person sees on the bot's Home tab."""
    _call(token, "views.publish", json={"user_id": slack_user_id, "view": view})


def post_with_pdf(token: str, channel: str, text: str, filename: str, pdf: bytes) -> None:
    """Upload `pdf` to `channel` with `text` as the message that comes with it (one post, the file attached).

    Slack's upload is three calls: ask for an upload address, send the bytes there, then complete it into the channel."""
    ticket = _call(token, "files.getUploadURLExternal", data={"filename": filename, "length": str(len(pdf))})
    sent = _post(ticket["upload_url"], content=pdf)
    if sent.status_code != 200:
        raise SlackError(f"Slack's upload address answered HTTP {sent.status_code}.")
    _call(
        token,
        "files.completeUploadExternal",
        json={"files": [{"id": ticket["file_id"], "title": filename}], "channel_id": channel, "initial_comment": text},
    )
