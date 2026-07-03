# D&D Character Forge — repo guidance

<!-- Orientation for Claude Code sessions in this repo. Deeper detail lives in the docs
     linked under "Free" below — read those; don't duplicate them here. -->

## Wiring  <!-- read before moving or renaming anything -->
- **Repo / branch:** github.com/DanForgedFrameworks/DnD_forge · main
- **Role:** Python D&D 5e character generator — engine (`forge/`) + web frontend (`frontend/`, `web/`), supporting 2014 ⇄ 2024 rulesets, SRD-based. Launch via `launch_forge.py` / `Forge.bat`.
- **Skills here:** /forge-qa-ship — static checks → deep integration sweep (derive-clean, 2014⇄2024 shape parity, companion-link integrity, SRD isolation, live endpoints per ruleset) → front-end wiring audit → data retro → (on your confirm) branch + PR.
- **Load-bearing** (never move/rename without updating the skill via /skill-evolve):
  - `.srd2024_src` submodule — the SRD source; keep SRD data isolated (forge-qa-ship checks this)
  - `forge/` engine · `launch_forge.py` — entry point
- **Free** (deeper docs — read for detail, safe to move): `ARCHITECTURE.md`, `HANDOVER.md`, `ISSUES.md`, `README.md`, `docs/`, `samples/`, `output/`.

<!-- Add repo-wide rules / skill config blocks below this header as needed. -->
