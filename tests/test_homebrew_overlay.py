"""The `_homebrew/` overlay merges over SRD data in every edition.

Confirms the Hoopak (a homebrew double weapon) resolves through the same
`SRDRepository.get("equipment", ...)` path the engine uses, and that the
overlay does not disturb the base SRD entries it sits alongside.

Run from anywhere:  python tests/test_homebrew_overlay.py
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
        repo = SRDRepository(edition, data_root=DATA_ROOT)

        hoopak = repo.get("equipment", "hoopak")
        if not hoopak or hoopak.get("name") != "Hoopak":
            print(f"FAIL[{edition}]: Hoopak did not resolve from the overlay")
            ok = False
            continue
        if hoopak.get("damage", {}).get("damage_dice") != "1d6":
            print(f"FAIL[{edition}]: Hoopak stats missing/wrong: {hoopak.get('damage')}")
            ok = False

        # overlay must not shadow the base SRD weapons it lives beside
        quarterstaff = repo.get("equipment", "quarterstaff")
        if not quarterstaff or quarterstaff.get("name") != "Quarterstaff":
            print(f"FAIL[{edition}]: base SRD Quarterstaff lost after overlay merge")
            ok = False

        print(f"OK[{edition}]: Hoopak resolves; base SRD intact")

    print("\nOK" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
