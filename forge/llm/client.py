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


DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class LLMClient:
    """Provider-aware client for the Forge's creative stages.

    Provider is config-driven (`config/forge_config.json` -> llm.provider): "gemini"
    (default for the forge — reads GEMINI_API_KEY) or "anthropic" (reads ANTHROPIC_API_KEY).
    Both expose the same `complete_json` / `complete_json_loose` API so callers don't change.
    """

    def __init__(self, model: str | None = None, max_tokens: int | None = None) -> None:
        cfg = _llm_config()
        self.provider = (cfg.get("provider") or "anthropic").lower()
        self.max_tokens = max_tokens or cfg.get("max_tokens", DEFAULT_MAX_TOKENS)
        if self.provider == "gemini":
            import os
            from google import genai  # lazy: only when Gemini is the active provider

            self.model = model or cfg.get("model", DEFAULT_GEMINI_MODEL)
            self._genai = genai
            self._client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        else:
            import anthropic  # lazy: non-LLM code/tests don't need the dependency

            self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
            self.model = model or cfg.get("model", DEFAULT_MODEL)

    # -- Gemini path (JSON mode + tolerant parse; engine validates downstream) ----------
    def _gemini_json(self, system: str, user: str) -> dict:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system + "\n\nReturn ONLY a single JSON object. No prose, no code fences.",
            response_mime_type="application/json",
            max_output_tokens=self.max_tokens,
        )
        resp = self._client.models.generate_content(model=self.model, contents=user, config=config)
        text = (getattr(resp, "text", None) or "").strip()
        if not text:
            raise RuntimeError("no text returned by Gemini (possibly filtered)")
        return _loads_tolerant(text)

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        """Return a JSON object. Anthropic: STRICT structured outputs against `schema`.
        Gemini: JSON mode (shape anchored by the prompt; validate downstream).
        """
        if self.provider == "gemini":
            return self._gemini_json(system, user)
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
        """Return a JSON object WITHOUT a strict grammar (shape anchored by the prompt).
        Tolerantly parsed, with one model-side repair retry. Validate downstream.
        """
        if self.provider == "gemini":
            try:
                return self._gemini_json(system, user)
            except Exception as e:
                if not repair:
                    raise
                return self._gemini_json(system + f"\n\nThe previous output was invalid JSON ({e}). Return only a single valid JSON object.", user)

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
