"""The Slack listener: a long-running process that receives the DM button presses over Socket Mode (it dials out to Slack,
so no public address is needed) and hands them to `slack.services.interactions`. Run it beside the API:

    make slack-dev        (or: python -m slack.listener from server/)

It needs both tokens (SLACK_BOT_TOKEN and SLACK_APP_TOKEN, see docs/SLACK_SETUP.md); without them it says so and stays up
idle, so `make dev` and `make prod-up` are not held up. The production stack runs it as the `slack` service
(docker-compose.yml). There is no logic here: it only turns Slack's payloads into calls.
"""
import re
import threading

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from core.config import get_settings
from slack import blocks
from slack.services import interactions


def build_app(bot_token: str, verify: bool = True) -> App:
    """`verify` makes Bolt check the token with Slack when the app is built; tests turn it off to stay offline."""
    app = App(token=bot_token, token_verification_enabled=verify)

    def tell(client, user: str, channel: str | None, text: str) -> None:
        """Show a message only the person who pressed can see (in their DM, or as a DM from the bot for a form)."""
        if channel:
            client.chat_postEphemeral(channel=channel, user=user, text=text)
        else:
            client.chat_postMessage(channel=user, text=text)

    @app.action(blocks.STATUS_ACTION)
    def on_status(ack, body, client):
        """The status dropdown: the chosen option's value is "<task id>|<status>"."""
        ack()
        user, channel = body["user"]["id"], (body.get("channel") or {}).get("id")
        task_id, to = body["actions"][0]["selected_option"]["value"].split("|")
        if blocks.needs_reason(to):  # Blocked, or back to To Do: ask for the reason first
            view, problem = interactions.reason_view(user, task_id, to)
            if problem:
                interactions.reset_card(task_id)
                return tell(client, user, channel, problem)
            return client.views_open(trigger_id=body["trigger_id"], view=view)
        if problem := interactions.move(user, task_id, to, None):
            tell(client, user, channel, problem)

    @app.action(blocks.COMMENT_ACTION)
    def on_comment(ack, body, client):
        ack()
        user, channel = body["user"]["id"], (body.get("channel") or {}).get("id")
        view, problem = interactions.comment_view(user, body["actions"][0]["value"])
        if problem:
            return tell(client, user, channel, problem)
        client.views_open(trigger_id=body["trigger_id"], view=view)

    @app.view("wb_comment_submit")
    def on_comment_submit(ack, body, client, view):
        text = (view["state"]["values"]["comment"]["text"]["value"] or "").strip()
        if not text:
            return ack(response_action="errors", errors={"comment": "Write a comment first."})
        ack()
        if problem := interactions.comment(body["user"]["id"], view["private_metadata"], text):
            tell(client, body["user"]["id"], None, problem)

    @app.view_closed("wb_reason")
    def on_reason_closed(ack, view):
        """The reason form was cancelled: the dropdown still shows the choice that was never made, so redraw the card."""
        ack()
        interactions.reset_card(view["private_metadata"].split("|")[0])

    @app.view("wb_reason")
    def on_reason(ack, body, client, view):
        reason = (view["state"]["values"]["reason"]["text"]["value"] or "").strip()
        if not reason:
            return ack(response_action="errors", errors={"reason": "Write a reason first."})
        ack()
        task_id, to = view["private_metadata"].split("|")
        if problem := interactions.move(body["user"]["id"], task_id, to, reason):
            tell(client, body["user"]["id"], None, problem)

    return app


def main(wait_if_unconfigured: bool = False) -> None:
    """Run the listener. Without the two tokens it says so; with `wait_if_unconfigured` it then stays up doing nothing,
    because the production stack starts it with `docker compose up --wait`, which treats a container that exits as a
    failure, and an unconfigured Slack must not stop the rest of the stack starting."""
    settings = get_settings()
    if not settings.slack_configured or not settings.slack_app_token.startswith("xapp-"):
        print("Slack listener not started: set SLACK_BOT_TOKEN and SLACK_APP_TOKEN in .env (see docs/SLACK_SETUP.md).")
        if wait_if_unconfigured:
            threading.Event().wait()
        return
    print("Slack listener starting (Socket Mode).")
    SocketModeHandler(build_app(settings.slack_bot_token), settings.slack_app_token).start()


if __name__ == "__main__":
    main(wait_if_unconfigured=True)
