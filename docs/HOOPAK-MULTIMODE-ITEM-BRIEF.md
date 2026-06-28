# Hoopak multi-mode item — brief

**Status:** open / handback to main chat
**Date:** 2026-06-28
**Scope:** make the kender Hoopak survive the forge as a single first-class item that
retains all of its modes (staff, sling, bullroarer), instead of being flattened to a
generic "Sling".

---

## Symptom

A kender forged in the Studio shows, in the **Equipment & Coin** panel, a generic
**"Sling"** + **"Sling bullets (20)"** instead of a **Hoopak**. The item has been:

- **Flattened to one mode** — only the sling survives. The **staff/quarterstaff** mode
  and the **bullroarer** (whirled whistling/signal) mode are gone.
- **Renamed off the canon** — the name "Hoopak" has disappeared, so the homebrew item
  can never be matched back to it.
- **Not offered in the picker** — the "+ Item" control is free-text; there is no Hoopak
  to choose.

The homebrew Hoopak exists in the data layer (`repo.get("equipment","hoopak")` resolves
in both editions — see `tests/test_homebrew_overlay.py`), but nothing in the
forge → save → display pipeline reads it.

---

## Root causes (each separately addressable)

**1. The homebrew Hoopak is never consumed by the forge.**
The forge builds gear from each class's/background's `starting_equipment` list
(`starting_gear()` in `forge/engine/rules_mode.py`), never from the global equipment
table. Nothing calls `get("equipment","hoopak")`, so the overlay item is an orphan.
*Fix direction:* give the overlay a consumer — a gear-resolution step that recognises
"Hoopak" and pulls the catalog entry.

**2. Strict mode wipes AI-written gear; the AI's relaxed-mode gear decomposes it.**
- In **strict** mode, `_enforce_gear` (`forge/engine/rules_mode.py`) replaces the whole
  list with by-the-book class+background gear (no Hoopak).
- In **relaxed** mode, the AI free-writes gear and rendered the hoopak as its most
  legible component — a plain "Sling" + bullets — because nothing tells it the Hoopak is
  a single canonical item.
*Fix direction:* a canonicalisation/alias pass that collapses "sling (kender)",
"forked staff", etc. back into one "Hoopak" entry, plus a forge instruction to keep
iconic species items intact.

**3. No alias/canonicalisation layer maps names ↔ the catalog.**
Nothing recognises "Hoopak" (or its parts) and binds it to the overlay's stats.
Free-text in, free-text out.
*Fix direction:* an equipment-name normaliser keyed on `index`/`name`/aliases, run
during forge and on save.

**4. The display is name-only and has no concept of "modes."**
The Codex renders the strings in `pc.equipment`; there is **no equipment API** and no UI
for an item with several attack/use profiles. Even a correctly-named Hoopak shows as one
inert line, not staff/sling/bullroarer.
*Fix direction:* render multi-mode items (the staff & sling already exist as `actions`;
the bullroarer needs a home).

**5. The "+ Item" picker can't surface homebrew.**
It is a free-text add with no catalog behind it (no equipment route in
`forge/web/app.py`).
*Fix direction:* an equipment lookup endpoint + a picker that includes `_homebrew` items.

---

## Data-model gap (the core of the request)

The Hoopak is **one item with three modes**, and nothing models that as a unit:

| Mode | Mechanic | Current status |
|------|----------|----------------|
| **Staff** (quarterstaff / spiked end) | 1d6 / 1d8 bludgeoning melee, Topple | exists only as a hand-written `action`; dropped on forge |
| **Sling** (forked end) | 1d4, 30/120 ranged, needs bullets | the *only* part that survived — but mislabelled as a separate "Sling" |
| **Bullroarer** (swung to whoop / whistle) | non-damage **signal**, audible ~600 ft | **not modelled anywhere** — overlay only mentions it in `special[]` prose |

The overlay entry (`data/srd/_homebrew/equipment.json`) carries the staff/sling stats and
bullroarer flavour text, but as **one weapon row with free-text `special[]`** — there is
no structured `modes[]` array the forge or UI can iterate. So even when it *is* consumed,
the bullroarer has nowhere to render and the modes can't be presented as options.

---

## Acceptance criteria ("fixed" looks like)

1. Forge a kender → the gear list shows **one "Hoopak"**, not a loose Sling.
2. That Hoopak exposes **all three modes** (staff attack, sling attack, bullroarer
   signal) — in `actions` and/or a modes view.
3. It **survives both rules modes** (strict doesn't delete it; relaxed doesn't
   decompose it).
4. It is **selectable** from "+ Item" (catalog-backed), and selecting it brings its
   stats/modes.
5. "Sling bullets" remains as its ammunition, linked to the sling mode rather than to a
   standalone Sling.

---

## Decisions the main chat must make

- **Where the bullroarer lives** in the schema — extend the equipment item with a
  structured `modes[]`, or keep it as an `action` + a flavour tag.
- **Canonicalisation scope** — Hoopak-only quick fix, or a general species-item alias
  table (kender hoopak today, others later).
- **Strict-mode policy** — allow whitelisted homebrew/species items as *additive*
  starting gear, vs. the current wholesale replace.
- **How far to build the catalog/picker now** — full equipment API + picker, vs. defer
  (just stop the decomposition and keep name-driven display).

---

## Reference points (where to look)

- `data/srd/_homebrew/equipment.json` — the Hoopak overlay entry (staff/sling stats +
  bullroarer in `special[]`).
- `forge/canon/srd_repository.py` — `_apply_homebrew()` merges the overlay; this is the
  only place the Hoopak is currently reachable.
- `forge/engine/rules_mode.py` — `starting_gear()` (gear source) and `_enforce_gear()`
  (strict wipe).
- `forge/agents/autofill.py` — relaxed-mode gear objectification (free-text path).
- `forge/web/app.py` — web routes; note the absence of any equipment endpoint.
- `tests/test_homebrew_overlay.py` — proves the overlay resolves; extend for the
  consumer once it exists.
- Worked precedent: `output/_live_pc_kender.json` (Pippet) — hand-patched Hoopak with
  staff/sling `actions`; kept only because she is `rulesMode: relaxed`.
