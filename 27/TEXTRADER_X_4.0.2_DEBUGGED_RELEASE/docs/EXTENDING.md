# Extending TEXTRADER X

This is the honest version of "future-proofing": not a claim that nothing will
ever need to change, but three extension points designed so that adding
something new never means rewriting what already works.

## 1. Switching or adding an LLM provider

No package install is required to switch — every provider talks plain HTTP.

```bash
# Local, no API key, no internet:
export OLLAMA_MODEL=llama3.1        # or qwen2.5, deepseek-r1, ...
textrader llm set ollama
textrader llm test

# Any API-key vendor (OpenAI, or any OpenAI-compatible endpoint —
# OpenRouter, Groq, Together, a self-hosted vLLM server, ...):
export OPENAI_API_KEY=sk-...
export OPENAI_BASE_URL=https://openrouter.ai/api/v1   # optional, defaults to OpenAI
textrader llm set openai

# Anthropic:
export ANTHROPIC_API_KEY=sk-ant-...
textrader llm set anthropic
```

Same three actions are available from the admin panel's **AI Provider** tab.

To add a vendor that isn't OpenAI-shaped or Ollama-shaped, write one class in
`trader/adapters/llm.py` implementing `complete(system, user, **kwargs) -> str`
and register it: `register_factory("my_vendor", lambda: MyVendorLLM())`. Agents
1–3 never import a vendor SDK directly — they only call `LLMAdapter`, so this
never touches agent code.

## 2. Adding an external data/research source

Two ways, both stdlib-only (no dependency to install just to add a source):

```bash
# Just a link — the system fetches and text-extracts it for research use:
textrader connector add some_report --url https://example.com/report --purpose research

# A real API — key stays in an env var, never written to disk:
export GLASSNODE_API_KEY=...
textrader connector add onchain --base-url https://api.glassnode.com/v1 \
    --api-key-env GLASSNODE_API_KEY --purpose market_data
```

Anything in the codebase — the research engine, the knowledge base, a future
data-reader adapter — can then do `get_connector("onchain").fetch(...)`
without knowing whether it's hitting a real API or reading a webpage.

## 3. Adding a panel module

`GET /api/modules` in `trader/web/server.py` is the single source of truth for
the admin panel's sidebar. It already lists the modules that are reserved but
not yet built (backtesting lab, multi-account, notifications, plugin
marketplace, audit export) so the roadmap is visible in the panel itself
rather than hidden in a backlog. Building one of them means: add the routes,
flip its `status` to `"active"`, done — no sidebar/template rewrite.

## What this section is *not*

It is not a claim that the system needs no further engineering, and it is not
a substitute for real integration work (a real broker adapter, a real paid
data feed) once you have the credentials for them — see
`FINAL_RELEASE_REPORT.md` for what is still mock/paper-only today.
