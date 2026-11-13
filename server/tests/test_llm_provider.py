"""The language-model provider: picks the host from the environment settings and returns the JSON answer.
The network is never touched: `_post` is replaced by a fake that records the request and returns a canned answer."""
import json

import pytest

from core.config import settings
from core.exceptions import AppError
from standups.llm import provider

SCHEMA = {"type": "object", "properties": {"items": {"type": "array"}}}


@pytest.fixture
def configure(monkeypatch):
    def _set(**values):
        for name in ("llm_provider", "llm_model", "llm_api_key", "llm_base_url"):
            monkeypatch.setattr(settings, name, values.get(name, ""))
    return _set


@pytest.fixture
def fake_post(monkeypatch):
    calls = []

    def install(answer):
        def post(url, headers, body):
            calls.append({"url": url, "headers": headers, "body": body})
            return answer
        monkeypatch.setattr(provider, "_post", post)
        return calls
    return install


def chat(content, finish="stop"):
    return {"choices": [{"message": {"content": content}, "finish_reason": finish}]}


def test_groq_is_called_with_the_key_the_model_and_the_schema(configure, fake_post):
    configure(llm_provider="groq", llm_model="some-model", llm_api_key="k-1")
    calls = fake_post(chat(json.dumps({"items": []})))

    assert provider.complete_json("hello", SCHEMA) == {"items": []}

    call = calls[0]
    assert call["url"] == provider.GROQ_URL and call["headers"] == {"Authorization": "Bearer k-1"}
    assert call["body"]["model"] == "some-model" and call["body"]["messages"] == [{"role": "user", "content": "hello"}]
    assert call["body"]["response_format"]["json_schema"]["schema"] == SCHEMA


def test_an_openai_compatible_host_uses_its_own_base_url_and_needs_no_key(configure, fake_post):
    configure(llm_provider="OpenAI_Compatible", llm_model="local", llm_base_url="http://127.0.0.1:11434/v1/")
    calls = fake_post(chat('{"items": [1]}'))

    assert provider.complete_json("hi", SCHEMA) == {"items": [1]}
    assert calls[0]["url"] == "http://127.0.0.1:11434/v1/chat/completions" and calls[0]["headers"] == {}


def test_anthropic_is_asked_to_call_one_tool_and_its_input_is_the_answer(configure, fake_post):
    configure(llm_provider="anthropic", llm_model="some-claude", llm_api_key="k-2")
    calls = fake_post({"stop_reason": "tool_use", "content": [
        {"type": "text", "text": "ok"}, {"type": "tool_use", "name": "submit_tasks", "input": {"items": ["x"]}},
    ]})

    assert provider.complete_json("hi", SCHEMA) == {"items": ["x"]}

    call = calls[0]
    assert call["url"] == provider.ANTHROPIC_URL and call["headers"]["x-api-key"] == "k-2"
    assert call["body"]["tools"][0]["input_schema"] == SCHEMA
    assert call["body"]["tool_choice"] == {"type": "tool", "name": "submit_tasks"}


@pytest.mark.parametrize("values,missing", [
    ({}, "LLM_PROVIDER"),
    ({"llm_provider": "nonsense"}, "LLM_PROVIDER"),
    ({"llm_provider": "groq", "llm_api_key": "k"}, "LLM_MODEL"),
    ({"llm_provider": "groq", "llm_model": "m"}, "LLM_API_KEY"),
    ({"llm_provider": "anthropic", "llm_model": "m"}, "LLM_API_KEY"),
    ({"llm_provider": "openai_compatible", "llm_model": "m"}, "LLM_BASE_URL"),
], ids=["nothing set", "unknown provider", "no model", "groq no key", "anthropic no key", "compatible no url"])
def test_a_missing_setting_is_named_and_nothing_is_sent(configure, fake_post, values, missing):
    configure(**values)
    calls = fake_post({})

    with pytest.raises(AppError) as err:
        provider.complete_json("hi", SCHEMA)

    assert err.value.code == "llm_not_configured" and err.value.status_code == 501 and missing in err.value.message
    assert calls == []


@pytest.mark.parametrize("answer", [
    chat('{"items": []}', finish="length"),
    chat("not json"),
    chat("[1, 2]"),
    {"choices": []},
], ids=["cut off", "not json", "not an object", "no choices"])
def test_an_unusable_openai_style_answer_is_a_502(configure, fake_post, answer):
    configure(llm_provider="groq", llm_model="m", llm_api_key="k")
    fake_post(answer)

    with pytest.raises(AppError) as err:
        provider.complete_json("hi", SCHEMA)

    assert (err.value.code, err.value.status_code) == ("llm_failed", 502)


@pytest.mark.parametrize("answer", [
    {"stop_reason": "max_tokens", "content": []},
    {"content": [{"type": "text", "text": "no tool"}]},
], ids=["cut off", "no tool call"])
def test_an_unusable_anthropic_answer_is_a_502(configure, fake_post, answer):
    configure(llm_provider="anthropic", llm_model="m", llm_api_key="k")
    fake_post(answer)

    with pytest.raises(AppError) as err:
        provider.complete_json("hi", SCHEMA)

    assert (err.value.code, err.value.status_code) == ("llm_failed", 502)


def test_a_failed_request_is_a_502_that_does_not_echo_the_response(monkeypatch):
    class Response:
        status_code = 429
        text = "secret detail from the provider"

    monkeypatch.setattr(provider.httpx, "post", lambda *a, **k: Response())

    with pytest.raises(AppError) as err:
        provider._post("http://x", {}, {})

    assert err.value.status_code == 502 and "429" in err.value.message and "secret" not in err.value.message
