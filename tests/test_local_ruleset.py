"""The `dnd5e-2024-local` ruleset overlays the local PHB extraction into optionLists, while
the SRD-only rulesets NEVER carry it (the shippable build is unaffected). When the local data
is absent (a clean clone — it's gitignored), the local ruleset degrades gracefully to SRD.

Run:  python tests/test_local_ruleset.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from forge.ruleset import Ruleset  # noqa: E402
from forge.ruleset import local_data as L  # noqa: E402

_LOCAL_KEYS = ("classFeaturesByClass", "weaponMasteries", "languages", "multiclassing")


def main() -> int:
    ok = True

    # 1) SRD-only rulesets must never expose the local-only blocks.
    for slug in ("dnd5e-2014", "dnd5e-2024"):
        ol = Ruleset(slug).option_lists()
        leaked = [k for k in _LOCAL_KEYS if k in ol]
        if leaked:
            print(f"FAIL[{slug}]: local keys leaked into an SRD ruleset: {leaked}")
            ok = False

    # 2) The local ruleset overlays the data when present, else degrades to SRD-only.
    local = Ruleset("dnd5e-2024-local").option_lists()
    if L.available():
        missing = [k for k in _LOCAL_KEYS if k not in local]
        if missing:
            print(f"FAIL: local ruleset missing blocks despite data present: {missing}")
            ok = False
        if not (local.get("weaponMasteries") or {}).get("properties"):
            print("FAIL: weaponMasteries.properties empty")
            ok = False
        if len(local.get("feats", [])) < len(Ruleset("dnd5e-2024").option_lists().get("feats", [])):
            print("FAIL: local feats not richer than SRD 2024")
            ok = False
        print(f"local data present — overlay verified ({len(local.get('feats', []))} feats, "
              f"{len(local.get('languages', []))} languages)")
    else:
        leaked = [k for k in _LOCAL_KEYS if k in local]
        if leaked:
            print(f"FAIL: local keys present without any data file: {leaked}")
            ok = False
        print("local data absent — graceful SRD-only degrade verified")

    print("\nOK" if ok else "\nFAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
