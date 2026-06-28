# Hand-back: art engine — consistent 4-state portrait SET + class-aware scenes

Built against `docs/ART-ENGINE-BRIEF.md`. Back-end only — **no front-end file was edited**, and
`build_prompt()` stays byte-for-byte identical to `computePrompt()` (the §3 invariant holds; the test
re-asserts it). Everything new rides as **DATA on `character.art`**, written by deterministic forge-time
enrichment, so the live preview and the engine prompt remain the same string.

## What changed (files)
- `forge/agents/art.py`
  - **Image provider is now OpenAI `gpt-image-1.5`** (config `image.provider == "openai"`). The Gemini/Imagen
    backends were removed — OpenAI matched the recorded Rutkowski/Tyler-Jacobson house style; Gemini rendered
    the same prompt as smoother "digital illustration." `_BACKENDS` is now just `{stub, openai}` (no silent
    fallback — if OpenAI is unavailable, regenerate manually).
  - Backends take `(prompt, seed=None, *, reference_image: bytes | None = None)`. `stub` accepts-and-ignores
    it; **`openai` honours it** — when a reference is supplied it calls `images.edit` with the anchor PNG and
    an instruction to keep the same face/build/gender/colouring and change only pose/action/framing/environment.
    The `openai` backend reads `image.openaiModel` (default `gpt-image-1`, falls back if the configured id is
    unavailable) and `image.openaiSize` (default `1024x1024`).
  - `generate_portrait(..., reference_image=None)` — forwards the reference to the backend.
  - **`generate_portrait_set(character, *, anchor_state="at-rest", anchor_image=None, seed=None, backend=None)`**
    — Item 6. Locks appearance + class beats (idempotent), generates the anchor (or reuses supplied bytes),
    then generates the other three conditioned on the anchor's bytes. Returns `{state: slot}` for all four.
  - **`lock_appearance(character)`** — Item 6. Ensures `art.appearance` carries an explicit, stable gender
    (from `art.gender`, else detected from the prose, else `androgynous` for PCs; genderless creatures are
    left untouched). Idempotent.
  - **`CLASS_STATE_BEATS` + `apply_class_beats(character)`** — Item 7. Fills `art.stateBeats` from the
    character's class/role (rogue, wizard, barbarian, cleric, fighter, ranger, bard, paladin, sorcerer,
    warlock, druid, monk) **unless `art.stateBeats` is already set**. `build_prompt` already reads
    `art.stateBeats`, so no prose logic moved and no front-end change is needed. in-conversation beats are
    written to read as *actively talking* (mid-conversation, speaking and gesturing toward someone off-frame);
    beats no longer conjure a phantom animal companion.
  - **`apply_companion(character)`** — carries a pet/animal companion into **every** state. `art.companion`
    is a non-rendered DATA field (e.g. "a large grey wolf"); the helper weaves it into `art.appearance` (an
    existing rendered field) so the companion appears *alongside* the character in all four prompts, not just
    at-rest. Idempotent; no-op when unset. `build_prompt` is unchanged (reads `art.appearance`).
- `forge/agents/autofill.py` — runs `lock_appearance` + `apply_companion` + `apply_class_beats` at the end of
  **both** assembly paths (statblock and PC), so the data is baked in at forge time.
- `forge/web/app.py` — new endpoint **`POST /art/set`** mirroring `/art`'s from-store persistence + JSON
  error handling.
- `config/forge_config.json` — `image.provider` set to `openai`; `openaiModel`/`openaiSize` added; Gemini
  keys removed.
- `tests/test_art.py` — added `test_portrait_set`, `test_class_beats`, `test_lock_appearance`, `test_companion`;
  the existing byte-for-byte invariant test is unchanged and still green.

## Front-end contract (for the build chat — NOT implemented here)

### Generate all four (one consistent person)
`POST /art/set`
```jsonc
// request — provide EITHER a saved id OR an inline character
{ "id": "hane-structured",        // or: "character": { ...full Character... }
  "anchorState": "at-rest",       // optional, default "at-rest" — which state anchors the set
  "seed": 1234 }                  // optional
// response
{ "portraits": {
    "at-rest":         { "prompt": "…", "imageUrl": "http://localhost:5000/art/<id>/at-rest.png", "seed": 1234 },
    "in-conversation": { "prompt": "…", "imageUrl": "…/in-conversation.png", "seed": 1234 },
    "in-battle":       { "prompt": "…", "imageUrl": "…/in-battle.png", "seed": 1234 },
    "travelling":      { "prompt": "…", "imageUrl": "…/travelling.png", "seed": 1234 }
} }
```
Errors surface as JSON: `400` (bad `anchorState`), `404` (unknown `id`), `502`
`{ "error": "image_generation_failed", "message": "…" }`.

### Per-state regenerate (existing)
`POST /art { id|character, state, tweak?, seed? }` → `{ prompt, imageUrl, seed }` — unchanged.

### Anchor picker / regenerate-from-chosen-anchor
The anchor is the visual source of truth for the set. Two-call flow the build chat should use:
1. Regenerate the chosen state on its own: `POST /art { id, state: "<chosen>", tweak?, seed? }`.
2. Rebuild the rest to match it: `POST /art/set { id, anchorState: "<chosen>" }`.

`/art/set` **reuses an already-generated anchor PNG on disk as-is** (it does not regenerate the anchor when
`output/portraits/<id>/<anchorState>.png` exists) and conditions the other three on it. For a first-time
"Generate all" with no images yet, the anchor (`at-rest` by default) is generated fresh, then the rest.

**UI suggestion:** "Generate all" → `POST /art/set`; a per-portrait "regenerate" → `POST /art`; an anchor
picker (radio over the four states) that drives `anchorState` in the rebuild call.

## Notes / constraints
- Set-conditioning uses the `openai` backend (`images.edit` with the anchor PNG); `stub` ignores the
  reference image (tests use `stub`). There is no Gemini fallback by design.
- OpenAI's image API exposes no usable image seed here, so `seed` round-trips as a prompt token, not pixels.
- `lock_appearance` only forces a gender on player characters; creatures with no gender signal in their
  appearance are left exactly as authored.
- House style is locked Rutkowski/Tyler-Jacobson in `FIXED_TAIL` (unchanged); OpenAI `gpt-image-1.5` renders
  it as the gritty painterly oil-painting figure-in-scene the reference images define.

## How to verify
```
.venv_forge\Scripts\python tests\test_art.py          # all green incl. set/beats/lock/companion
# live (needs OPENAI_API_KEY + provider openai): POST /art/set for one character,
# eyeball that the four images are the same person/gender; spot-check class beats + companion in the prompts.
```
