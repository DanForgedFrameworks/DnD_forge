# Homebrew overlay

Edition-shared additions and overrides that sit *on top of* the canonical SRD
data. `SRDRepository._load()` merges these over the per-edition SRD files at
read time, so anything here is reachable through the same
`repo.get(category, key)` calls the engine already uses.

- **One file per canonical category**, named for the category key — e.g.
  `equipment.json`, `spells.json`. (See the category keys in
  `forge/canon/srd_repository.py`.)
- **Merge rule:** each overlay entry replaces the SRD entry sharing its
  `index` (or `name` if no index); otherwise it is appended.
- **Why it lives here, not in `data/srd/<edition>/`:**
  `scripts/fetch_srd_data.py` rewrites the per-edition directories on every
  re-import, which would wipe homebrew. This directory is never touched by that
  script, so overlays survive.
- Tag overlay entries with `"homebrew": true` and a `"source"` so they're easy
  to spot on a sheet.

Current contents:

- `equipment.json` — **Hoopak**, the kender forked walking-staff (quarterstaff +
  sling double weapon). Covered by `tests/test_homebrew_overlay.py`.
