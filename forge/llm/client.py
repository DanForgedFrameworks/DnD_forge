"""Thin Claude API client for the Forge's creative stages.

Uses the official `anthropic` SDK. Defaults to claude-opus-4-8 (override in
config/forge_config.json -> llm.model). Reads ANTHROPIC_API_KEY from the
environment or a local .env file.

Structured output uses the Messages API `output_config.format` (json_schema), so
the response is guaranteed to parse against the supplied schema — no repair pass.
"""
from __future__ import annotations

import json
from pathlib import Path

try:  # load .env if present; harmless if python-dotenv isn't installed
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG = _REPO_ROOT / "config" / "forge_config.json"

DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_MAX_TOKENS = 8000


def _llm_config() -> dict:
    try:
        return json.loads(_CONFIG.read_text(encoding="utf-8")).get("llm", {})
    except Exception:
        return {}


class LLMClient:
    def __init__(self, model: str | None = None, max_tokens: int | None = None) -> None:
        import anthropic  # lazy: non-LLM code/tests don't need the dependency

        cfg = _llm_config()
        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        self.model = model or cfg.get("model", DEFAULT_MODEL)
        self.max_tokens = max_tokens or cfg.get("max_tokens", DEFAULT_MAX_TOKENS)

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        """Return a JSON object constrained to `schema` via structured outputs."""
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"model refused the request: {getattr(resp, 'stop_details', None)}")
        text = next((b.text for b in resp.content if b.type == "text"), None)
        if not text:
            raise RuntimeError("no text block returned by the model")
        return json.loads(text)
