"""
LLM adapter — provider-agnostic (OI-08).

The default provider is `mock`: a deterministic, rule-based pseudo-LLM that
returns schema-conformant outputs derived from the supplied context. This makes
the runtime fully runnable out-of-the-box without any API keys, while keeping
the agent boundary exactly as designed.

To plug a real provider (OpenAI, Anthropic, Ollama, ...), implement `LLMProvider`
and register it via `set_provider(name, instance)`. Agents never touch the
provider directly — they call `LLMAdapter.complete(...)`.
"""
from __future__ import annotations

import json
import hashlib
import os
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol


class LLMProvider(Protocol):
    name: str
    def complete(self, system: str, user: str, *,
                 max_tokens: int = 1024, temperature: float = 0.0,
                 seed: Optional[int] = None) -> str: ...


# ----------------------------------------------------------------------------
# Mock LLM — deterministic, no external dependencies
# ----------------------------------------------------------------------------

class MockLLM:
    name = "mock"

    def __init__(self, *, seed: int = 7):
        self._seed = seed

    def complete(self, system: str, user: str, *,
                 max_tokens: int = 1024, temperature: float = 0.0,
                 seed: Optional[int] = None) -> str:
        # Deterministic digest of the inputs — same inputs ⇒ same output.
        h = hashlib.sha256(f"{system}|{user}|{seed or self._seed}".encode()).hexdigest()
        # The mock LLM does not try to be smart; it returns a JSON envelope whose
        # specific shape is decided by the caller (agent). Here we return a
        # generic "digest" object that agents can interpret.
        return json.dumps({
            "digest": h[:16],
            "system_tag": system[:48],
            "user_tag": user[:64],
            "mock": True,
        })


def _http_post_json(url: str, payload: dict, headers: dict, timeout: float = 60.0) -> dict:
    """Stdlib-only JSON POST (no `requests`/`openai`/`ollama` package required,
    so switching providers never requires installing anything beyond what
    ships with Python)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM HTTP {e.code}: {body[:500]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"LLM connection failed ({url}): {e.reason}") from e


# ----------------------------------------------------------------------------
# Ollama — local LLM, no API key, no internet required
# ----------------------------------------------------------------------------

class OllamaLLM:
    """Local model served by Ollama (https://ollama.com).

    Activate with: TEXTRADER_LLM_PROVIDER=ollama, OLLAMA_HOST (default
    http://localhost:11434), OLLAMA_MODEL (e.g. llama3.1, qwen2.5, deepseek-r1).
    Nothing else to install — Ollama exposes a plain HTTP API.
    """
    name = "ollama"

    def __init__(self, model: str = "llama3.1", host: str | None = None):
        self.model = model
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")

    def complete(self, system: str, user: str, *,
                 max_tokens: int = 1024, temperature: float = 0.0,
                 seed: Optional[int] = None) -> str:
        out = _http_post_json(
            f"{self.host}/api/chat",
            {
                "model": self.model,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens,
                             **({"seed": seed} if seed is not None else {})},
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}],
            },
            headers={},
        )
        return (out.get("message") or {}).get("content", "")


# ----------------------------------------------------------------------------
# OpenAI-compatible — covers OpenAI itself AND any provider that mirrors its
# /v1/chat/completions shape (OpenRouter, Groq, Together, vLLM, LM Studio, ...)
# ----------------------------------------------------------------------------

class OpenAICompatibleLLM:
    """Activate with: TEXTRADER_LLM_PROVIDER=openai, OPENAI_API_KEY,
    OPENAI_BASE_URL (default https://api.openai.com/v1 — point this at any
    OpenAI-compatible endpoint to switch vendors without code changes),
    OPENAI_MODEL (default gpt-4o-mini)."""
    name = "openai"

    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None,
                 base_url: str | None = None):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")

    def complete(self, system: str, user: str, *,
                 max_tokens: int = 1024, temperature: float = 0.0,
                 seed: Optional[int] = None) -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        out = _http_post_json(
            f"{self.base_url}/chat/completions",
            {
                "model": self.model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **({"seed": seed} if seed is not None else {}),
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}],
            },
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        return out["choices"][0]["message"]["content"] or ""


# ----------------------------------------------------------------------------
# Anthropic (Claude) — native Messages API
# ----------------------------------------------------------------------------

class AnthropicLLM:
    """Activate with: TEXTRADER_LLM_PROVIDER=anthropic, ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL (default claude-sonnet-4-6)."""
    name = "anthropic"

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None,
                 base_url: str | None = None):
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.base_url = (base_url or os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")).rstrip("/")

    def complete(self, system: str, user: str, *,
                 max_tokens: int = 1024, temperature: float = 0.0,
                 seed: Optional[int] = None) -> str:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        out = _http_post_json(
            f"{self.base_url}/messages",
            {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
        )
        parts = out.get("content", [])
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


# ----------------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------------

_PROVIDERS: dict[str, LLMProvider] = {"mock": MockLLM()}

# name -> (factory, human description) for providers that need lazy/optional
# construction (they may require env vars that aren't set yet at import time).
_PROVIDER_FACTORIES: dict[str, Callable[[], LLMProvider]] = {
    "mock": lambda: MockLLM(),
    "ollama": lambda: OllamaLLM(model=os.getenv("OLLAMA_MODEL", "llama3.1")),
    "openai": lambda: OpenAICompatibleLLM(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini")),
    "anthropic": lambda: AnthropicLLM(model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")),
}


def register_provider(name: str, provider: LLMProvider) -> None:
    _PROVIDERS[name] = provider


def register_factory(name: str, factory: Callable[[], LLMProvider]) -> None:
    """Add a brand-new provider type without touching this file again — e.g.
    a custom internal model server. See docs/EXTENDING.md."""
    _PROVIDER_FACTORIES[name] = factory


def available_providers() -> list[str]:
    return sorted(_PROVIDER_FACTORIES)


def get_provider(name: str) -> LLMProvider:
    if name in _PROVIDERS:
        return _PROVIDERS[name]
    if name in _PROVIDER_FACTORIES:
        instance = _PROVIDER_FACTORIES[name]()
        _PROVIDERS[name] = instance
        return instance
    raise KeyError(f"LLM provider {name!r} not registered. Available: {available_providers()}")


@dataclass
class LLMAdapter:
    """Thin facade used by all 3 agents and the decision engine/validator.

    The adapter enforces schema-validation discipline: callers are expected to
    pass the expected output schema name; on parse/validation failure, the
    agent is responsible for downgrading to WAIT (invariant I5).
    """
    provider_name: str = "mock"

    @property
    def provider(self) -> LLMProvider:
        return get_provider(self.provider_name)

    def complete(self, system: str, user: str, **kwargs) -> str:
        return self.provider.complete(system, user, **kwargs)

    def ping(self) -> dict:
        """Cheap connectivity/sanity check used by `textrader llm test` and the
        admin panel — never raises, always returns a status dict."""
        try:
            out = self.complete("Reply with exactly one word.", "Say OK.", max_tokens=8)
            return {"provider": self.provider_name, "ok": True, "sample": out[:80]}
        except Exception as e:  # noqa: BLE001 — surfaced to caller, not fatal
            return {"provider": self.provider_name, "ok": False, "error": str(e)}

    def complete_json(self, system: str, user: str, **kwargs) -> dict | None:
        """Convenience: parse the LLM output as JSON. Returns None on failure."""
        raw = self.complete(system, user, **kwargs)
        try:
            return json.loads(raw)
        except Exception:
            # Some real LLMs wrap JSON in ```json ... ``` fences; try to extract.
            s = raw.strip()
            if s.startswith("```"):
                s = s.strip("`")
                if s.lower().startswith("json"):
                    s = s[4:].strip()
                try:
                    return json.loads(s)
                except Exception:
                    return None
            return None
