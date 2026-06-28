# PC Progression (levelling) + Multiclass — engine handback

**Status: DONE (engine + endpoint + Level control).** Built in the engine chat, 2026-06-28.
Brief: [PC-PROGRESSION-MULTICLASS-BRIEF.md](PC-PROGRESSION-MULTICLASS-BRIEF.md).

This is the deterministic re-derivation half. A player can now change a PC's **level** in the
Studio and the engine re-derives the level-dependent numbers; the **multiclass** data model and
maths are in place and exercised by the endpoint. The only piece deliberately **left for the
front-end build chat** is the add/remove-**classes** editor UI (the contract for it is below, so
it can be wired without touching the engine).

---

## 1. What shipped

| Piece | Where |
|---|---|
| Re-derivation engine | `forge/engine/progression.py` (new) — `rederive(character, level=?, classes=?)` |
| Multiclass proficiency rules | `forge/engine/grants.py` — `MULTICLASS_PROFICIENCIES` + class-list-aware `resolve_pc_proficiencies` |
| Multiclass spell enforcement | `forge/engine/rules_mode.py` — `_enforce_spellcasting` now union-aware (best-effort) |
| Derive endpoint | `forge/web/app.py` — `POST /character/derive` |
| Level control (Studio) | `web/frontend/Character Forge - Prototype.dc.html` — number input + "what changed" note, `deriveLevel()` / `summariseChanges()` |
| Tests | `tests/test_progression.py` (new). `test_ruleset` / `test_rules_mode` / `test_art` still green |

Run the suite: `.venv_forge\Scripts\python tests\test_progression.py` (and the other three).

---

## 2. The derive endpoint — contract

`POST /character/derive`

**Request**
```jsonc
{
  "character": { /* a full Character object, kind:"character" */ },   // required
  "level":   9,                                                       // optional: single-class shortcut
  "classes": [{ "class": "wizard", "subclass": "evocation", "level": 5 },
              { "class": "cleric", "level": 3 }]                      // optional: the multiclass list
}
```
- Pass **`level`** to re-level a single-class PC (re-levels the primary class).
- Pass **`classes`** to set the whole class mix (this is what the class-list editor will send).
- Pass **neither** for an idempotent refresh (re-derive at the current level).

**Response**
```jsonc
{
  "character": { /* the re-derived character — same object, derived fields updated */ },
  "warnings":  [ { "level": "info|warning|error", "message": "…" } ],
  "changes":   {                       // only keys that actually changed are present
    "level":            { "from": 5, "to": 9 },
    "hp":               { "from": "32 (5d6 + 10)", "to": "56 (9d6 + 18)" },
    "proficiencyBonus": { "from": 3, "to": 4 },
    "hitDice":          { "from": 5, "to": 9 },
    "spellSlots":       { "from": {"1":4,"2":3,"3":2}, "to": {"1":4,"2":3,"3":3,"4":3,"5":1} },
    "saveDc":           { "from": 14, "to": 15 },
    "attackBonus":      { "from": 6, "to": 7 },
    "featuresGained":   [ { "class": "wizard", "level": 6, "name": "…" } ]
  }
}
```
`changes` drives the "what changed" line; `warnings` are the advisory/strict notes (relaxed never
removes anything, strict trims over-limit spells + regenerates gear, exactly as on `POST /character`).

**Does NOT persist.** The front-end saves via the existing `POST /character` once the player accepts.
Errors come back as JSON (`400 not_a_pc`, `422 derive_failed`), never a 500 page.

**Never clobbered:** exact ability scores, hand-picked cantrips/spells, equipment, portraits, art,
traits, name/id. Only the derived numbers move.

---

## 3. Data model — `pc.classes[]` (for the class-list editor)

Additive and **only materialised for real multiclass** (2+ classes), so single-class characters
stay byte-for-byte on disk.

- **Single-class** → unchanged: `pc.class`, `pc.subclass`, `pc.level`. No `pc.classes` field.
- **Multiclass** → `pc.classes = [{class, subclass, level}, …]` is the source of truth, **plus** the
  primary mirror is kept in sync for back-compat:
  - `pc.class` / `pc.subclass` mirror `pc.classes[0]`
  - `pc.level` = **sum** of the class levels (total character level)
  - `challenge` = `"— (level <total>)"`

The engine reads `pc.classes` when present, else synthesises a 1-element list from `pc.class`.
**The class-list editor should send the full list as `classes` to `/character/derive`** and never
hand-edit `pc.class`/`pc.level` — let the engine write the mirror back. When the list drops to one
class, the engine removes `pc.classes` again.

### Multiclass spellcasting shape (what the Play tab / spell picker should read)
- `spellcasting.slots` — the combined Spellcasting slots (PHB multiclass table = full-caster
  progression; computed from the **combined caster level**: full casters +level, paladin/ranger
  +level//2, warlock excluded).
- `spellcasting.pactSlots` — **separate** Warlock Pact Magic slots (only present when a warlock is in
  the mix; same `{level: {total, expended}}` shape).
- `spellcasting.perClass` — `[{class, ability, saveDc, attackBonus}]` per caster class (multiclass
  only). The headline `spellcasting.ability/saveDc/attackBonus` is the **primary** caster's.
- `pc.hitDicePools` — `[{die, total, remaining}]` breakdown when the dice are mixed (single-class
  keeps just `pc.hitDice`). `pc.classFeatures` — `[{name, class, level}]`, engine-owned (the LLM's
  flavour `traits[]` are left untouched).

### Spell picker (`GET /spells`) interop
Today `/spells` takes a single `class`+`level`. For multiclass the front-end can either call it
per-class and merge, or (cleaner follow-up) we add a combined mode — flag it if you want that and
I'll extend the endpoint. The engine's combined limits already exist in
`rules_mode._combined_limits`.

---

## 4. The Level control (already wired — don't duplicate)

In the Studio PC editor (`pcEditable` branch) there is now a **Level** number input next to
Background. On change it calls `deriveLevel(value)`, which `POST`s the draft to `/character/derive`,
lands the returned character as the draft, and shows a green "what changed" note (`pcDeriveNote`,
cleared on character load). Mirrors how the spell picker calls the bridge.

**For the class-list editor:** build the add/remove-classes UI in the same `pcEditable` block, have
each row carry `{class, subclass, level}`, and on any change call a sibling method (e.g.
`deriveClasses(list)`) that posts `{character, classes: list}` to `/character/derive` — reuse
`summariseChanges()` for the note. The Concept-Sheet free-text multiclass string (e.g.
"Ranger (Fey Wanderer) / Druid (Circle of Dreams)") can be parsed into that same list to seed it.

---

## 5. Known limitations (deliberate, documented)

- **Third-casters (Eldritch Knight / Arcane Trickster)** don't contribute to the combined caster
  level yet — they're subclass-driven on non-caster base classes and the SRD base entries carry no
  slot data. Full/half casters + warlock pact are correct. Easy follow-up via subclass detection.
- **Subclass feature *text*** isn't expanded — `featuresGained` lists the base-class Levels-table
  features (incl. the "choose a subclass feature" markers). Subclass-specific text lives in the
  Subclasses data; wire that in if the sheet needs the prose.
- **Multiclass Strict spell policing is best-effort** (union spell list, summed cantrip/leveled
  counts, max learnable level = max over classes). Relaxed (default) is advisory-only and exact.
- **Multiclass skill grants** from secondary classes (the odd +1 skill from Bard/Ranger/Rogue) are
  not auto-added — skills stay primary-class picks + background. Saving throws are primary-class only
  (correct).

Edition-native (2014 + 2024) is preserved throughout — the wizard/warlock Levels tables are read
from the character's own edition repo.
