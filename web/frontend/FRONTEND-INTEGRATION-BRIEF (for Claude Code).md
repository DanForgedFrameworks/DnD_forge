# Front-end integration brief — for Claude Code

Read this once. It's everything needed to get the Forge front-end working locally against the
bridge and to resolve the open decisions in a single pass (no file-by-file round-trips).

---

## 0. STATUS as of this handover (read first)

This `.dc.html` is bound to engine `main @ 2bd0a66` and is the current front-end. All six `[DECIDE]`
items below are **resolved**; the front-end work for the live-now ones is **already built into this
file** (mock-verified). What remains is gated on engine shapes not yet on `main`.

**Built + verified, live now:**
- Bridge adapter (integrated, `localStorage.forgeBridgeUrl`) — probe, rulesets, ruleset config, rail, forge, art.
- Starter rail reads `challenge` + `accent` (§5a, live).
- `POST /art` success → `POST /character` persists `portraits[state]` (§5b, live).
- PC editor: Class / Subclass / Race / Background dropdowns + **Race↔Species label flip**; creature **Type hidden for PCs**; "Player character" toggle / Category / Blank now create a real `pc{}` skeleton.

**Built defensively — dark until you ship the enriched shapes, then auto-lights-up:**
- **Subspecies** dropdown bound to `pc.subspecies`, filtered via `optionLists.subspeciesBySpecies[<species>]`.
- **Skill-choice picker** ("Skills — choose N"): reads `optionLists.classes[].{skillChoose, skillFrom}`, writes **only** `pc.skillChoices: [<index>,…]` (caps at N, resets on class change). Per decision **(B), engine derives** `saveProfs`/`skillProfs`/`proficiencies` on `POST /character` + the PC forge path — the front-end sets none of them.

**Decisions locked:** §3 integrated adapter canonical (retire `web/forge-bridge.js` + `fallback-data.js`); §5a done; §5b built; §5d advisory; §5e `/art/preview` off (preview == generated); §5f forge = replace-draft + switch to Studio.

**Waiting on your next engine batch (don't bind-live until you pin a new SHA):**
1. `optionLists.classes[]` enriched → `{index, name, saves, skillChoose, skillFrom, armor, weapons, tools}`
2. `optionLists.backgrounds[]` enriched → `{index, name, skills, tools, languages, abilityOptions, feat}`
3. `optionLists.subspeciesBySpecies` → `{ "<speciesIndex>": [{index,name}], … }`
4. `POST /forge {kind:"character"}` → full PC (`pc{}` + `spellcasting{}` + `saveProfs`/`skillProfs` + features with `source`), matching `samples/sample_pc.json`.
5. One open detail to confirm: after `POST /character` returns the **derived** character, the front-end should replace its draft with that returned object so the statblock immediately shows resolved saves/skills (assumed yes).

**Protocol (kills drift):** cite the engine `main` SHA before binding anything live; an engine shape
change names the endpoint + exact key; a front-end change is the single re-exported `.dc.html`.

---

Design (the front-end author) cannot see your repo edits, and you cannot see Design's project —
the human relays. So this brief is exhaustive on purpose. Where a decision is needed, it's marked
**[DECIDE]** with a recommended default.

---

## 1. What the front-end is
- `Character Forge - Prototype.dc.html` — a self-contained app with three surfaces: **Studio**
  (manual editor + live statblock), **Forge** (brain-dump → statblock + portrait set), **Codex**
  (print/PDF sheet). It is a "Design Component" (DC) HTML file.
- It loads two sibling files by **relative path**: `./support.js` (the DC runtime) and
  `./image-slot.js` (the drag-drop portrait fallback). All three must sit in the same folder.
- **No build step.** Open the HTML in a browser. Fonts load from Google Fonts CDN.
- Suggested repo home: `web/frontend/` (keep it distinct from the existing `web/forge-bridge.js`).

## 2. Run it locally (live mode)
1. `python -m forge.web.app`  → serves `http://127.0.0.1:5000`.
2. Open `web/frontend/Character Forge - Prototype.dc.html` via `file://` (double-click), **or**
   serve it from Flask same-origin.
3. On load it probes `GET /rulesets`. Success → top-right pill flips to **"Bridge live"** and it
   wires rulesets, the starter rail, forge, and live portraits. Failure → **"Local preview"**
   (bundled samples; everything still renders).
4. Override the bridge URL with `localStorage.forgeBridgeUrl` or `?bridge=http://host:port`.
5. **Mixed content:** an HTTPS-hosted copy cannot fetch `http://localhost` — it will stay in
   fallback. Live mode needs `file://` or Flask same-origin. (localhost-to-localhost is fine.)

## 3. The adapter is INTEGRATED — not `web/forge-bridge.js`
The working adapter lives **inside the DC's logic class** (methods `api`/`jpost`, `componentDidMount`
probe, `loadRuleset`, `refreshLibrary`, `loadServer`, `forgeViaBridge`, `genArt`, `portraitUrl`).
It uses localStorage key **`forgeBridgeUrl`**.

`web/forge-bridge.js` + `web/fallback-data.js` are a *separate*, non-integrated adapter (standalone
`ForgeBridge` class, key `forgeBaseUrl`, expects a global `window.computePrompt`). For THIS front-end
they are redundant — `computePrompt` is a method on the DC logic class, not a global.
- **[DECIDE] Which adapter is canonical?** Recommended: **keep the integrated one**;
  treat `web/forge-bridge.js`/`fallback-data.js` as a reference for a future plain-HTML embed, or
  delete them. If instead you want `forge-bridge.js` to be canonical, that's a front-end rewrite
  (expose `computePrompt` globally, route all calls through the instance, align the localStorage
  key) — say so and Design will do it. Don't wire both.

## 4. Exact shapes the front-end depends on (keep stable)
Verified against the live engine on `main`:
- `GET /rulesets` → `{rulesets:[{slug,label,extends}]}` — labels are shown in the selector.
- `GET /ruleset/<slug>` → `{slug,label,labels,abilityRules,statblock,optionLists}`.
  - `labels.species` drives the **Race↔Species** flip ("Race" 2014 / "Species" 2024).
  - `optionLists` keys: **`classes, subclassesByClass, species, subspecies, backgrounds, feats,
    conditions, creatureTypes, sizes`**. Entries are `{index,name}` (front-end binds
    `value=index`, `label=name`), except `sizes`/`creatureTypes` which are plain strings.
- `POST /forge {dump,ruleset,kind}` → `{character, warnings:[{level,message}]}` (level ∈
  error|warning|info → coloured Validation panel).
- `POST /art {character|id, state} → {prompt,imageUrl,seed}`. `imageUrl` is an absolute
  `http://localhost:5000/art/<id>/<state>.png`. One state per call.
- `GET /character` → `{characters:[{id,name,kind,ruleset,level}]}` (starter rail).
- `GET /character/<id>` → full Character. `POST /character` → save (runs `apply_derived`).
- `GET /art/<id>/<state>.png` → image bytes.
- `build_prompt` == the front-end's `computePrompt()` byte-for-byte (`include_cues` defaults off,
  so preview == generated).

## 5. Open decisions — resolve these while it's running locally
Front-loaded so we settle them in one go:

- **[DECIDE] a) Starter-rail metadata.** `GET /character` summaries omit `challenge` and a colour
  `accent`, so server creatures render as "… · CR —" with a default swatch. *Recommended:* add
  `challenge` (and optionally `accent`) to the list payload — cheap, and the rail already reads them.
- **[DECIDE] b) Portrait persistence.** The front-end sends the **current draft** as `character`
  to `POST /art` (so generation always reflects unsaved edits). On that path the engine writes the
  PNG but does **not** write `portraits[state]` back into the character JSON (only the `id` path
  does). Options: (i) front-end calls `POST /character` after a successful generate to persist the
  metadata; (ii) for server-backed characters, send `id` only. *Recommended:* (i) — keeps "generate
  from live draft" while persisting. Confirm and Design will wire the follow-up save.
- **[DECIDE] c) Subspecies editing.** The PC species dropdown binds to base `pc.species` (matches
  `optionLists.species`). Subspecies (e.g. high-elf) shows in the subtitle but isn't editable yet,
  though `optionLists.subspecies` exists. Decide whether to add a subspecies control and how
  subspecies filter per species (is there a species→subspecies map, or a flat list?).
- **[DECIDE] d) Ability-score rules.** `abilityRules` (point-buy budget/ranges, monster bounds) are
  served but the Studio ability editor doesn't enforce them — `validate()` warnings cover drift.
  Decide if the editor should hard-enforce or stay advisory.
- **[DECIDE] e) `/art/preview`.** Reserved in the adapter; client `computePrompt()` is the live
  per-keystroke preview. Wire `/art/preview` at generate-time only if you want the canonical
  `include_cues` check enforced (it would add the statblock-cue clause, diverging preview from the
  per-keystroke text). *Recommended:* leave off unless you want cues.
- **[DECIDE] f) Forge replace behaviour.** A successful `/forge` replaces the whole draft and
  switches to Studio; any prior in-session portraits for that slot are cleared. Confirm that's wanted
  (vs. merging into the current draft).

## 6. Acceptance checklist (self-verify locally)
- [ ] Pill shows **Bridge live**; ruleset selector lists 2014 / 2024 / homebrew with proper labels.
- [ ] Load a saved PC (or Lyra sample): Class / Subclass / Race / Background are **editable
      dropdowns**; switching 2014↔2024 flips the **Race↔Species** label.
- [ ] Changing a PC dropdown updates the live subtitle/statblock.
- [ ] Brain-dump → **Forge** → statblock populates + `warnings[]` render in the Validation panel.
- [ ] **Generate** on each portrait state → image appears; **Codex** shows it; reload still serves
      the PNG via its URL.
- [ ] Starter rail lists characters from `GET /character`.
- [ ] Monster Studio: Size / Type / Alignment dropdowns come from the ruleset (types title-cased).

## 7. How to send changes back
The front-end is a single file (`Character Forge - Prototype.dc.html`). Design edits it in their
project and re-exports. When you need a change, describe it against the **method names in §3** or the
**shapes in §4** so Design can apply it precisely. When you change an engine shape, name the endpoint
+ the exact key that changed — that's all Design needs to re-bind.
