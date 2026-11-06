"""Thin wrapper around the OpenAI API.

All calls go through here so that: the key is read only from the environment,
failures degrade gracefully (the deterministic layers still work), every
response that should be JSON is validated against a strict schema, and token
usage is counted for the eval CLI's fuzz budget.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections import OrderedDict
from typing import Any

from . import config

log = logging.getLogger("hiddenink.llm")

_client = None
_lock = threading.Lock()
_tokens_used = 0
_cache: OrderedDict[str, dict] = OrderedDict()
CACHE_SIZE = 500


class LLMUnavailable(RuntimeError):
    pass


def client():
    global _client
    if not config.openai_enabled():
        raise LLMUnavailable("OPENAI_API_KEY is not set.")
    with _lock:
        if _client is None:
            from openai import OpenAI
            _client = OpenAI(api_key=config.OPENAI_API_KEY, timeout=config.OPENAI_TIMEOUT, max_retries=2)
    return _client


def tokens_used() -> int:
    return _tokens_used


def _count(resp) -> None:
    global _tokens_used
    usage = getattr(resp, "usage", None)
    if usage is None:
        return
    with _lock:
        _tokens_used += int(getattr(usage, "total_tokens", 0) or 0)


_minimal_rejected = False  # set once the API refuses reasoning_effort="minimal"; "low" is used from then on
REASONING_MODELS = ("gpt-5", "gpt-6", "o3", "o4")


def _rejects_minimal(exc: Exception) -> bool:
    text = str(exc).lower()
    return getattr(exc, "status_code", None) == 400 and ("minimal" in text or "reasoning_effort" in text)


def json_call(system: str, user: Any, schema_name: str, schema: dict, model: str | None = None,
              max_tokens: int = 8000, reasoning_effort: str | None = None) -> dict:
    """Chat completion with a strict JSON schema. `user` may be a string or a content list (for images).

    Retries once with "low" if the API rejects reasoning_effort="minimal", and once with double the
    output limit if the answer was cut off or isn't valid JSON.
    """
    global _minimal_rejected
    model = model or config.OPENAI_TEXT_MODEL
    # Reasoning models accept an effort setting; older chat models reject it.
    effort = (reasoning_effort or config.OPENAI_REASONING_EFFORT) if model.startswith(REASONING_MODELS) else ""
    limit = max_tokens
    for _attempt in range(3):  # the first try, at most one effort fallback, at most one larger-limit retry
        if effort == "minimal" and _minimal_rejected:
            effort = "low"
        try:
            resp = client().chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={"type": "json_schema", "json_schema": {"name": schema_name, "strict": True, "schema": schema}},
                max_completion_tokens=limit,
                **({"reasoning_effort": effort} if effort else {}),
            )
        except Exception as exc:  # noqa: BLE001
            if effort == "minimal" and not _minimal_rejected and _rejects_minimal(exc):
                _minimal_rejected = True
                log.warning("reasoning_effort=minimal was rejected for %s; using low from now on", model)
                continue
            raise
        _count(resp)
        choice = resp.choices[0]
        if getattr(choice.message, "refusal", None):
            raise RuntimeError(f"Model refused: {choice.message.refusal}")
        cut_off = getattr(choice, "finish_reason", None) == "length"
        if not cut_off:
            try:
                return json.loads(choice.message.content or "")
            except json.JSONDecodeError:
                pass
        if limit != max_tokens:
            raise RuntimeError("Model output was cut off." if cut_off else "Model returned invalid JSON.")
        limit = max_tokens * 2
    raise RuntimeError("Model call failed after retries.")


# ---------- reusable answers: an in-memory LRU cache (per process; the demo keeps no database) ----------
def cache_key(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def cache_get(key: str) -> Any | None:
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return json.loads(json.dumps(_cache[key]))
    return None


def cache_put(key: str, value: Any) -> None:
    """Stores the model's output only, never the request or the API key."""
    with _lock:
        _cache[key] = json.loads(json.dumps(value))
        _cache.move_to_end(key)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)


def cached_json_call(system: str, user: Any, schema_name: str, schema: dict, **kw) -> dict:
    """json_call, but identical inputs return the identical answer (used by the scan layers).

    Models are not deterministic run to run, so without this the same file could get a
    different score each time it is scanned, and we would pay for it again. Not used where
    fresh output is wanted (the Red-Team payload writer).
    """
    key = cache_key(system, user, schema_name, kw.get("model") or config.OPENAI_TEXT_MODEL)
    hit = cache_get(key)
    if hit is not None:
        return hit
    out = json_call(system, user, schema_name, schema, **kw)
    cache_put(key, out)
    return json.loads(json.dumps(out))


def obj(properties: dict, required: list[str] | None = None) -> dict:
    """Helper for strict JSON schemas: every property required, no extras."""
    return {"type": "object", "properties": properties, "required": required or list(properties),
            "additionalProperties": False}
