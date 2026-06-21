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


def _loads_tolerant(text: str) -> dict:
    """Parse a JSON object out of model text: strip fences, isolate the outer {...},
    and forgive trailing commas."""
    import re

    s = (text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s).rstrip("`").strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start:end + 1]
    s = re.sub(r",(\s*[}\]])", r"\1", s)  # drop trailing commas
    return json.loads(s)


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
        """Return a JSON object constrained to `schema` via STRICT structured outputs.

        Use for small/medium schemas. Large, deeply-nested schemas overflow the
        structured-output grammar compiler ('compiled grammar is too large') — use
        `complete_json_loose` for those.
        """
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

    def complete_json_loose(self, system: str, user: str, *, repair: bool = True) -> dict:
        """Return a JSON object WITHOUT the strict grammar (no schema constraint).

        For large objects whose schema can't compile to a structured-output grammar.
        The shape is anchored by an embedded JSON template in the prompt instead; the
        response is tolerantly extracted and parsed, with one model-side repair retry.
        Validate the result yourself (jsonschema) downstream.
        """
        def _call(extra_user: str | None = None) -> str:
            msgs = [{"role": "user", "content": user}]
            if extra_user:
                msgs.append({"role": "user", "content": extra_user})
            resp = self.client.messages.create(
                model=self.model, max_tokens=self.max_tokens, thinking={"type": "adaptive"},
                system=system + "\n\nReturn ONLY a single JSON object. No prose, no code fences.",
                messages=msgs,
            )
            if resp.stop_reason == "refusal":
                raise RuntimeError(f"model refused the request: {getattr(resp, 'stop_details', None)}")
            return next((b.text for b in resp.content if b.type == "text"), "") or ""

        text = _call()
        try:
            return _loads_tolerant(text)
        except Exception as e:
            if not repair:
                raise
            fixed = _call(f"That was not valid JSON ({e}). Return the corrected, complete JSON object only.")
            return _loads_tolerant(fixed)
