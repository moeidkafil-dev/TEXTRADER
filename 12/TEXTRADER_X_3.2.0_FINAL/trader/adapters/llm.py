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


# ----------------------------------------------------------------------------
# OpenAI-style stub (registered but inactive by default — needs API key)
# ----------------------------------------------------------------------------

class OpenAICompatibleLLM:
    """Skeleton for an OpenAI-style chat completions provider.

    To activate: set env vars OPENAI_API_KEY, OPENAI_BASE_URL (optional),
    OPENAI_MODEL (default gpt-4o-mini). Requires `openai` package.
    """
    name = "openai"

    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None,
                 base_url: str | None = None):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    def complete(self, system: str, user: str, *,
                 max_tokens: int = 1024, temperature: float = 0.0,
                 seed: Optional[int] = None) -> str:
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:
            raise RuntimeError("openai package not installed") from e
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        resp = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=temperature,
            seed=seed,
        )
        return resp.choices[0].message.content or ""


# ----------------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------------

_PROVIDERS: dict[str, LLMProvider] = {"mock": MockLLM()}


def register_provider(name: str, provider: LLMProvider) -> None:
    _PROVIDERS[name] = provider


def get_provider(name: str) -> LLMProvider:
    if name not in _PROVIDERS:
        raise KeyError(f"LLM provider {name!r} not registered. Available: {list(_PROVIDERS)}")
    return _PROVIDERS[name]


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
