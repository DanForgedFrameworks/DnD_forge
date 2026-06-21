"""Persist a record of every /forge call so a run can be interrogated afterward.

Each forge (success OR failure) appends one JSON file under output/forge_log/, plus a
one-line summary to output/forge_log/index.jsonl. The record captures the request
(dump / ruleset / kind / rulesMode / flavour details), timing, any warnings, and the
full resulting character — everything needed to debug "why did this forge do that?".

These live under the gitignored output/ tree, so they never enter the repo.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "forge_log"


def _slug(s: str | None) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s or "unknown"


def log_forge(request_body: dict, result: dict | None, *, started: float,
              error: str | None = None) -> Path | None:
    """Write one forge record. `started` is a time.time() taken before the call."""
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        character = (result or {}).get("character") if isinstance(result, dict) else None
        warnings = (result or {}).get("warnings") if isinstance(result, dict) else None
        cid = (character or {}).get("id") or _slug((request_body or {}).get("dump"))[:40]

        record = {
            "schema": "forge-log/1",
            "requestedAt": now.isoformat(),
            "durationMs": int((time.time() - started) * 1000),
            "ok": error is None,
            "error": error,
            "request": {
                "dump": (request_body or {}).get("dump"),
                "ruleset": (request_body or {}).get("ruleset"),
                "kind": (request_body or {}).get("kind"),
                "rulesMode": (request_body or {}).get("rulesMode"),
                "details": (request_body or {}).get("details"),
            },
            "warnings": warnings or [],
            "characterId": cid,
            "character": character,
        }

        stamp = now.strftime("%Y%m%d-%H%M%S")
        path = _LOG_DIR / f"{stamp}-{cid}.json"
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

        summary = {
            "at": record["requestedAt"], "ms": record["durationMs"], "ok": record["ok"],
            "kind": record["request"]["kind"], "rulesMode": record["request"]["rulesMode"],
            "id": cid, "warnings": len(record["warnings"]), "error": error,
            "dump": (record["request"]["dump"] or "")[:80], "file": path.name,
        }
        with (_LOG_DIR / "index.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, ensure_ascii=False) + "\n")
        return path
    except Exception:
        return None  # logging must never break a forge
