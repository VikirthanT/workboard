"""Slack's refusals as the API's own errors, so a screen can say what is wrong with a channel in plain words."""
from core.exceptions import AppError
from slack.client import SlackError


def channel_error(err: SlackError) -> AppError:
    text = str(err)
    if "channel_not_found" in text:  # Slack says this too for a private channel the bot is not in
        return AppError(
            "channel_not_found",
            "Slack cannot find this channel. Check the channel id, and for a private channel invite the Work Board bot to it.",
            404,
        )
    if "not_in_channel" in text:
        return AppError("bot_not_in_channel", "The Work Board bot is not in this channel. Invite it, then try again.", 409)
    return AppError("slack_failed", f"Slack could not be asked about the channel. {text}", 502)
