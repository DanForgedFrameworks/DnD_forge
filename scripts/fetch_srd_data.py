"""Pull the open 5e SRD dataset into data/srd/<edition>/.

Source : https://github.com/5e-bits/5e-database  (the data behind dnd5eapi.co)
Editions: 2014 (SRD 5.1) and 2024 (SRD 5.2), English locale.
Licence : CC-BY-4.0 / OGL — fine for local / non-commercial use.

Uses only the Python standard library, so it runs before any pip install.

Usage:
    python scripts/fetch_srd_data.py            # both editions
    python scripts/fetch_srd_data.py 2014       # a single edition
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "data" / "srd"
EDITIONS = ("2014", "2024")
CONTENTS_API = "https://api.github.com/repos/5e-bits/5e-database/contents/src/{edition}/en"
HEADERS = {
    "User-Agent": "dnd-character-forge-fetch",
    "Accept": "application/vnd.github+json",
}


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def fetch_edition(edition: str) -> int:
    listing = json.loads(_get(CONTENTS_API.format(edition=edition)))
    files = [f for f in listing if f["name"].endswith(".json")]
    out_dir = DATA_ROOT / edition
    out_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for f in files:
        data = _get(f["download_url"])  # raw.githubusercontent.com (no API rate limit)
        (out_dir / f["name"]).write_bytes(data)
        total += len(data)
        print(f"  {f['name']:<45} {len(data):>11,} bytes")
    print(f"[{edition}] {len(files)} files, {total:,} bytes -> {out_dir}\n")
    return len(files)


def main(argv: list[str]) -> int:
    editions = argv or list(EDITIONS)
    for ed in editions:
        if ed not in EDITIONS:
            print(f"skip unknown edition {ed!r} (expected one of {EDITIONS})")
            continue
        print(f"== Fetching SRD {ed} ==")
        fetch_edition(ed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
