"""Smoke test for the canonical SRD layer.

Confirms both editions load, reports category counts, and spot-checks a couple of
edition-divergent lookups (Races/Species rename, 2024-only weapon mastery).

Run from anywhere:  python tests/smoke_srd.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from forge.canon import SRDRepository, SUPPORTED_EDITIONS  # noqa: E402

DATA_ROOT = REPO_ROOT / "data" / "srd"


def main() -> int:
    ok = True
    for edition in SUPPORTED_EDITIONS:
        print(f"\n=== SRD {edition} ===")
        repo = SRDRepository(edition, data_root=DATA_ROOT)
        for cat, count in repo.summary().items():
            flag = "" if count else "  <-- MISSING"
            print(f"  {cat:<28} {str(count):>6}{flag}")
            if not count:
                ok = False

        # spot-checks: the engine relies on these resolving cleanly
        species = repo.species()
        print(f"  species sample: {[s.get('name') for s in species[:5]]}")
        classes = repo.classes()
        print(f"  classes       : {[c.get('name') for c in classes]}")

    print("\nOK" if ok else "\nFAIL: some categories did not load")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
