# D&D Character Forge

An agentic pipeline that turns a player's input — free-text brain dump, guided form,
interview, or full/partial randomisation — into a complete, **rules-legal D&D 5e
character**, with generated personality, backstory and (later) imagery.

Built for local use. Not a commercial product, so canonical rules data stays within
the openly-licensed SRD (CC-BY-4.0 / OGL).

## Core principle

> **Agents propose, the engine disposes.**

The LLM/agent layer makes *choices* and writes *narrative*. A deterministic Python
**rules engine**, backed by a local canonical SRD database, computes every derived
number (proficiency bonus, HP, AC, saves, spell slots, DCs) and validates legality.
The LLM never invents the maths.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design, decisions, and roadmap.

## Quick start (local)

```bash
# 1. (optional) create a venv
python -m venv .venv_forge
.venv_forge\Scripts\activate        # Windows
# pip install -r requirements.txt    # needed for engine/web stages, not for data pull

# 2. Pull the canonical SRD data (both editions)
python scripts/fetch_srd_data.py

# 3. Smoke-test the canonical data layer
python tests/smoke_srd.py
```

## Layout

| Path | Purpose |
|------|---------|
| `config/` | Runtime config (active LLM provider, rulesets, paths) |
| `data/srd/{2014,2024}/` | Pulled canonical SRD JSON (gitignored, re-fetchable) |
| `scripts/` | Reproducible utilities (data fetch, etc.) |
| `forge/canon/` | Edition-aware access layer over the SRD data |
| `forge/engine/` | Deterministic rules engine *(to build)* |
| `forge/schema/` | JSON Schemas for the character object *(to build)* |
| `forge/pipeline/` | Stage orchestrator *(to build, adapted from Catalyst)* |
| `forge/web/` | Flask backend *(to build)* |
| `tests/` | Smoke tests |

## Licensing & attribution

The **2024** spell and slot data is generated from the **System Reference Document 5.2.1**
(© Wizards of the Coast LLC), used under the
[Creative Commons Attribution 4.0 License](https://creativecommons.org/licenses/by/4.0/), via the
[downfallx/dnd-5e-srd-markdown](https://github.com/downfallx/dnd-5e-srd-markdown) conversion.
Regenerate it with `python scripts/convert_srd2024_md.py`. Full credit and the pinned source commit
are in [`data/srd/2024/ATTRIBUTION.md`](data/srd/2024/ATTRIBUTION.md).
