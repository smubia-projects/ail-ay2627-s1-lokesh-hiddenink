"""json_call against a fake OpenRouter client: reasoning effort fallback, cut-off retries and the client config."""
from types import SimpleNamespace

import pytest

from app import config, llm


def _fake_client(responses, seen):
    def create(**kw):
        seen.append({"model": kw.get("model"), "max_tokens": kw.get("max_tokens"),
                     "effort": (kw.get("extra_body") or {}).get("reasoning", {}).get("effort")})
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        content, finish = r
        return SimpleNamespace(usage=None, choices=[SimpleNamespace(
            finish_reason=finish, message=SimpleNamespace(content=content, refusal=None))])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


class _BadRequest(Exception):
    status_code = 400


def test_client_points_at_openrouter(monkeypatch):
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(llm, "_client", None)
    c = llm.client()
    assert str(c.base_url).rstrip("/") == "https://openrouter.ai/api/v1"
    monkeypatch.setattr(llm, "_client", None)


def test_minimal_effort_falls_back_to_low(monkeypatch):
    seen = []
    monkeypatch.setattr(llm, "_minimal_rejected", False)
    responses = [_BadRequest("Unsupported value: 'minimal' for reasoning.effort"), ('{"ok": 1}', "stop"), ('{"ok": 2}', "stop")]
    monkeypatch.setattr(llm, "client", lambda: _fake_client(responses, seen))
    assert llm.json_call("s", "u", "x", {}, model="openai/gpt-5.4-nano", reasoning_effort="minimal") == {"ok": 1}
    assert llm.json_call("s", "u", "x", {}, model="openai/gpt-5.4-nano", reasoning_effort="minimal") == {"ok": 2}
    assert [s["effort"] for s in seen] == ["minimal", "low", "low"]  # remembered for the process


def test_cut_off_answer_is_retried_with_double_the_limit(monkeypatch):
    seen = []
    responses = [('{"text": "trunc', "length"), ('{"text": "full"}', "stop")]
    monkeypatch.setattr(llm, "client", lambda: _fake_client(responses, seen))
    monkeypatch.setattr(config, "OPENROUTER_REASONING_EFFORT", "")
    assert llm.json_call("s", "u", "x", {}, model="openai/gpt-4o-mini", max_tokens=1500) == {"text": "full"}
    assert [s["max_tokens"] for s in seen] == [1500, 3000]
    assert seen[0]["effort"] is None  # reasoning disabled: no `reasoning` sent

    responses[:] = [("not json", "stop"), ("still not json", "stop")]
    with pytest.raises(RuntimeError, match="invalid JSON"):
        llm.json_call("s", "u", "x", {}, model="openai/gpt-4o-mini", max_tokens=100)
