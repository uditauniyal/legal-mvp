"""LLM and embedding calls, routed through OpenRouter.

Every call to the outside world goes through this file. That is deliberate:
it means instrumentation has exactly one place to live, and the provider
pinning cannot be forgotten at some call site.

WHAT CHANGED FROM THE OPENAI-DIRECT VERSION
    - base_url points at OpenRouter; the OpenAI SDK is otherwise unchanged
    - every request carries a `provider` block pinning the serving company,
      forbidding fallbacks, and requiring that our parameters are supported
      rather than silently dropped
    - each call returns usage metadata (which provider actually served it,
      what it cost) so a run log can record it

THE SILENT-DROP TRAP
    OpenRouter omits unsupported parameters rather than erroring. Send
    temperature=0 to a model that does not support it and it simply vanishes —
    you would write "temperature=0" in a paper and it would not be true.
    `require_parameters: true` turns that silence into a loud failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from core.config import (
    EMBED_MODEL,
    EMBED_PROVIDER,
    GEN_MODEL,
    GEN_PROVIDER,
    GEN_TEMPERATURE,
    OPENAI_BASE_URL,
    OPENROUTER_API_KEY,
    SEED,
    provider_block,
)

# The OpenAI SDK insists on a non-empty key at construction time. If .env has
# no key yet, we pass a placeholder so that `import app` still works and
# core.config.check() can report the problem properly instead of the module
# blowing up at import.
client = OpenAI(
    base_url=OPENAI_BASE_URL,
    api_key=OPENROUTER_API_KEY or "MISSING_OPENROUTER_API_KEY",
    default_headers={"X-Title": "legal-mvp"},
)


@dataclass
class CallMeta:
    """What actually happened on a call — for the run log."""

    model: str = ""
    provider_name: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    generation_id: str | None = None
    ok: bool = True
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _meta_from(response: Any, model: str) -> CallMeta:
    """Pull provider and usage off an OpenRouter response.

    OpenRouter adds a `provider` field to the response body. The SDK does not
    model it, so it lands in model_extra.
    """
    meta = CallMeta(model=model)
    try:
        meta.generation_id = getattr(response, "id", None)
        extra = getattr(response, "model_extra", None) or {}
        meta.provider_name = extra.get("provider")
        usage = getattr(response, "usage", None)
        if usage is not None:
            meta.prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            meta.completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        served = getattr(response, "model", None)
        if served:
            meta.model = served
    except Exception:  # metadata must never break a working call
        pass
    return meta


def embed_texts(texts: list[str]) -> tuple[list[list[float]], CallMeta]:
    """Embed a batch of texts.

    Returns (vectors, meta). Batching matters: one call for 64 chunks instead
    of 64 calls.

    NOTE the return type changed from `list[list[float]]` to a tuple so the
    caller can log which provider served it. Call sites must unpack.
    """
    resp = client.embeddings.create(
        model=EMBED_MODEL,
        input=texts,
        extra_body={"provider": provider_block(EMBED_PROVIDER)},
    )
    return [d.embedding for d in resp.data], _meta_from(resp, EMBED_MODEL)


def embed_one(text: str) -> tuple[list[float], CallMeta]:
    """Convenience wrapper for the single-query case."""
    vectors, meta = embed_texts([text])
    return vectors[0], meta


def chat(
    messages: list[dict],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    json_mode: bool = False,
) -> tuple[str, CallMeta]:
    """One chat completion.

    json_mode=True asks for a JSON object back. Combined with
    require_parameters, an unsupported provider errors instead of quietly
    returning prose we would then fail to parse.
    """
    model = model or GEN_MODEL
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": GEN_TEMPERATURE if temperature is None else temperature,
        "seed": SEED,
        "extra_body": {"provider": provider_block(GEN_PROVIDER)},
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(**kwargs)
    content = resp.choices[0].message.content or ""
    return content, _meta_from(resp, model)


def chat_json(messages: list[dict], max_tokens: int = 2048, model: str | None = None) -> str:
    """Backwards-compatible wrapper used by agents/intake.py.

    Kept so existing call sites keep working during the migration. New code
    should call `chat()` directly and log the returned CallMeta.
    """
    content, _ = chat(messages, model=model, max_tokens=max_tokens, json_mode=True)
    return content
