"""One call to whichever language model the environment names (LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, LLM_BASE_URL).

`complete_json(prompt, schema)` returns the model's answer as a dict shaped by `schema`. groq and openai_compatible
(for example a local Ollama) speak the OpenAI chat format; anthropic is asked to call one tool whose input is the
schema, which is how Claude returns strict JSON. Changing provider or model is an `.env` change, not a code change.

shortcut: no retry on a rate limit or a cut-off answer, the caller sees a 502 and the sync can simply run again.
"""
import json

import httpx

from core.config import get_settings
from core.exceptions import AppError

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
PROVIDERS = ("groq", "anthropic", "openai_compatible")
MAX_TOKENS = 8000  # reasoning models (Groq's gpt-oss, for one) count their thinking toward this, and a cut-off answer is an error
TIMEOUT_SECONDS = 90.0


def complete_json(prompt: str, schema: dict) -> dict:
    settings = get_settings()
    provider = settings.llm_provider.strip().lower()
    if provider not in PROVIDERS:
        raise AppError("llm_not_configured", f"LLM_PROVIDER must be one of {', '.join(PROVIDERS)}.", 501)
    needed = {"LLM_MODEL": settings.llm_model}
    if provider == "openai_compatible":
        needed["LLM_BASE_URL"] = settings.llm_base_url
    else:
        needed["LLM_API_KEY"] = settings.llm_api_key
    missing = [name for name, value in needed.items() if not value.strip()]
    if missing:
        raise AppError("llm_not_configured", f"Set {', '.join(missing)} to use {provider}.", 501)

    if provider == "anthropic":
        return _anthropic(settings.llm_api_key, settings.llm_model, prompt, schema)
    url = GROQ_URL if provider == "groq" else settings.llm_base_url.rstrip("/") + "/chat/completions"
    return _openai_style(url, settings.llm_api_key, settings.llm_model, prompt, schema)


def _post(url: str, headers: dict, body: dict) -> dict:
    """The only place that touches the network. The answer's text is never echoed into an error."""
    try:
        res = httpx.post(url, headers=headers, json=body, timeout=TIMEOUT_SECONDS)
    except httpx.HTTPError as err:
        raise AppError("llm_failed", "The language model could not be reached.", 502) from err
    if res.status_code >= 400:
        raise AppError("llm_failed", f"The language model answered HTTP {res.status_code}.", 502)
    return res.json()


def _bad_answer(why: str) -> AppError:
    return AppError("llm_failed", f"The language model's answer was unusable: {why}.", 502)


def _openai_style(url: str, key: str, model: str, prompt: str, schema: dict) -> dict:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "tasks", "strict": True, "schema": schema}},
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
    }
    data = _post(url, {"Authorization": f"Bearer {key}"} if key else {}, body)
    choice = (data.get("choices") or [{}])[0]
    if choice.get("finish_reason") == "length":
        raise _bad_answer("it was cut off")
    try:
        answer = json.loads(choice["message"]["content"])
    except (KeyError, TypeError, json.JSONDecodeError):
        raise _bad_answer("it was not JSON") from None
    if not isinstance(answer, dict):
        raise _bad_answer("it was not a JSON object")
    return answer


def _anthropic(key: str, model: str, prompt: str, schema: dict) -> dict:
    body = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
        "tools": [{"name": "submit_tasks", "description": "Submit the tasks for the manager.", "input_schema": schema}],
        "tool_choice": {"type": "tool", "name": "submit_tasks"},
    }
    data = _post(ANTHROPIC_URL, {"x-api-key": key, "anthropic-version": "2023-06-01"}, body)
    if data.get("stop_reason") == "max_tokens":
        raise _bad_answer("it was cut off")
    for block in data.get("content") or []:
        if block.get("type") == "tool_use" and isinstance(block.get("input"), dict):
            return block["input"]
    raise _bad_answer("it did not call the tool")
