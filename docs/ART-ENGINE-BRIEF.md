# Brief: art engine — consistent 4-state portrait SET + class-aware scenes

**This is a self-contained task brief for a dedicated chat.** You do not need the rest of the project's
conversation history. Read top to bottom, confirm §8, then build §5. Your job is **back-end art work in
`forge/agents/art.py` + one bridge endpoint**. You are **NOT editing the front-end** (§7), and you must
**preserve an invariant** (§3) — read it carefully.

---

## 1. What this project is (one paragraph)
The **D&D Character Forge** (repo root: `C:\Users\celt_\OneDrive\VLE e-Learning Documents\D&D Character Forge`,
GitHub `DanForgedFrameworks/DnD_forge`) is a local Flask + Python tool that turns a description into a
rules-legal D&D 5e character sheet **plus a four-state portrait set** (at-rest / in-conversation / in-battle
/ travelling). Portraits are produced by `forge/agents/art.py`: `build_prompt(character, state)` assembles a
deterministic prompt; `generate_portrait(character, state)` calls a pluggable image backend and saves a PNG.

## 2. The mission (two items)
- **Item 6 — portrait-set consistency (the gender-drift fix).** Today each of the four portraits is
  generated independently, so the character's face/build/**gender** drift between them. Fix it: generate the
  four as a **SET** — one **anchor** image first (default = at-rest), then condition the other three on that
  anchor image so they depict the *same person*. Lock an explicit appearance (incl. gender) so it can't
  wander. Regenerate must let the user pick which image is the anchor.
- **Item 7 — class-aware scene beats.** Make the per-state action contextual by class/role (a rogue skulks
  and whispers, a wizard confers with a familiar, a barbarian roars) instead of the current generic beat.

## 3. THE INVARIANT YOU MUST NOT BREAK (read before coding)
`build_prompt()` reproduces the front-end prototype's `computePrompt()` **byte-for-byte** — "the engine
prompt == the live preview" is a load-bearing project guarantee. **Therefore do NOT add class logic into
`build_prompt()`'s prose assembly** (it would silently diverge from the front-end, which you are not allowed
to edit). Instead:
- `build_prompt()` already reads two per-character DATA fields: **`art.stateBeats[state]`** (overrides the
  action beat) and **`art.appearance`**. Carry both Item 6 (locked appearance + gender) and Item 7
  (class-specific beats) as **DATA on the character**, written by a deterministic enrichment step at forge
  time. Because both `build_prompt` and `computePrompt` read that same data, they stay identical — no
  front-end change needed. **This is the whole trick; respect it.**
- Do **not** change `FIXED_TAIL` (the Rutkowski/Tyler-Jacobson house style is locked).

## 4. What already exists (reuse this)
- `build_prompt(character, state, *, adjustment=None, include_cues=False)` — segments: subject (PC pulls
  class/species from `pc{}`), `art.appearance`/`outfit`/`pose`, scene = `{action}; {STATE_CAM[state]}` where
  `action = art.stateBeats[state] or STATE_ACT[state]`, environment via `STATE_ENV_PREFIX[state]`, mood,
  style, `FIXED_TAIL`.
- `generate_portrait(character, state, *, adjustment, seed, backend)` → builds prompt, calls
  `backend(prompt, seed) -> {"image_bytes", "seed"}`, saves `output/portraits/<id>/<state>.png`, writes
  `character.portraits[state] = {prompt, imageUrl, seed}`.
- Backends in `_BACKENDS`: `stub`, `gemini` (Imagen — no image input), **`gemini-flash`** (the configured
  provider; `gemini-2.5-flash-image` via `client.models.generate_content(contents=[prompt], ...)` — this is
  **multimodal and CAN take an input image**, which is what makes set-conditioning possible).
- Bridge: `POST /art {id|character, state}` → `generate_portrait` → `{prompt, imageUrl, seed}`; persists back
  to the stored character; `GET /art/<id>/<state>.png` serves bytes. Mirror this handler's shape.
- Run/test: venv = `.venv_forge/Scripts/python.exe`; provider `gemini-flash` works (Gemini billing on,
  ~$0.04/image); `tests/test_art.py` exists and must stay green.

## 5. Deliverables
**(a) Extend the backend signature to accept a reference image** (optional, back-compatible):
`backend(prompt, seed=None, *, reference_image: bytes | None = None)`. In `gemini_flash_backend`, when
`reference_image` is set, pass it alongside the prompt:
`contents=[prompt, types.Part.from_bytes(data=reference_image, mime_type="image/png")]` — instructing the
model to keep the same character/face/appearance. `stub_backend` and `gemini_backend` accept the kwarg and
**ignore** it (document: set-conditioning requires `gemini-flash`).

**(b) `generate_portrait_set(character, *, anchor_state="at-rest", anchor_image=None, seed=None, backend=None)`:**
1. If `anchor_image` is None, generate the anchor state first (normal `generate_portrait`) and read back its
   PNG bytes; else use the supplied bytes (the regenerate-from-chosen-anchor path).
2. Generate the other three states with `reference_image=<anchor bytes>` so they match.
3. Save all four, populate `character.portraits`, return `{state: slot}` for all four.
Keep it backend-pluggable (tests pass `stub`).

**(c) Appearance + gender lock** (deterministic helper, e.g. `lock_appearance(character)`): ensure
`art.appearance` carries an explicit, stable physical description **including gender** so every prompt in the
set agrees. If the auto-fill agent already authored appearance/gender, normalise/keep it; if gender is
missing, make it explicit (the agent should supply it — this step enforces presence and stability). Document
where it runs (forge path / before a set generation).

**(d) Class-aware beats** — add `CLASS_STATE_BEATS = {role: {state: beat}}` (rogue, wizard, barbarian,
cleric, fighter, ranger, bard, etc.) and a deterministic `apply_class_beats(character)` that, when
`art.stateBeats` isn't already user-set, fills `character.art.stateBeats` from the character's class/role.
**Run it in the forge path so the beats live in character DATA** (preserving §3). `build_prompt` needs no
change — it already consults `art.stateBeats`.

**(e) Bridge endpoint** `POST /art/set {id|character, anchorState?, seed?}` in `forge/web/app.py` →
`generate_portrait_set(...)` → `{"portraits": {state: slot}}`. Mirror `/art`'s `from_store` persistence and
JSON-error handling. (For regenerate-with-chosen-anchor, the build chat can re-call `/art` for the new
anchor then `/art/set` with that anchor; expose `anchorState` so the chosen state seeds the set.)

**(f) Front-end contract** (document only — do NOT implement): the build chat will surface "Generate all"
(→ `POST /art/set`), per-state regenerate (existing `POST /art`), and an anchor picker. Write the
request/response contract into the hand-back note.

## 6. Acceptance tests
- **Set with `stub` backend:** `generate_portrait_set` writes 4 PNGs and populates all four `portraits`
  slots; the three non-anchor calls receive `reference_image` (assert via a spy backend).
- **Class beats:** `apply_class_beats` on a rogue sets rogue-flavoured `art.stateBeats`; a character with a
  pre-set `art.stateBeats` is left untouched. Confirm `build_prompt` output is **unchanged** for a character
  with no class beats (byte-for-byte invariant holds).
- **Live (behind `GEMINI_API_KEY`):** a set of four visibly-consistent images (same person/gender) for one
  character; spot-check class beats show up in the prompts.

## 7. Don'ts
- Don't edit `web/frontend/Character Forge - Prototype.dc.html` (front-end serialized to the build chat).
- Don't change `build_prompt()`'s prose logic or `FIXED_TAIL` — keep `build_prompt == computePrompt`.
- Don't make set-conditioning depend on Imagen/stub (only `gemini-flash` supports image input).

## 8. Inputs to confirm before starting
1. `tests/test_art.py` green before you start: `.venv_forge/Scripts/python.exe tests/test_art.py`.
2. `GEMINI_API_KEY` in `.env`; `config/forge_config.json` `image.provider == "gemini-flash"` (live tests).
3. Confirm you understand §3 (the byte-for-byte invariant) before writing any code.

## 9. Definition of done
`generate_portrait_set()` produces four visibly-consistent portraits (anchor + 3 conditioned on it), with an
explicit locked appearance/gender; `POST /art/set` exposes it; class/role-specific beats are written into
`character.art.stateBeats` at forge time (so the front-end preview stays identical with no front-end edit);
`tests/test_art.py` green + new set/beat tests; `build_prompt` byte-for-byte unchanged for the no-beats case.
