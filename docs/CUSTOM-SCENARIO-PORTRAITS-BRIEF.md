# Brief: custom-scenario portraits beyond the fixed four (art-engine, Phase B)

**Self-contained task brief for the ART-ENGINE chat.** You own `forge/agents/art.py` + the `/art*` endpoints. This
adds **user-defined extra portraits** (a 5th, 6th… in any scenario the player describes) on top of the existing four
fixed states — **without losing the originals** and **without breaking the byte-for-byte `build_prompt == computePrompt`
invariant** or the set-conditioning. The front-end UI is the BUILD chat's job (contract in §6).

---

## 1. Why
Players want portraits in their own scenarios/poses, not just at-rest / in-conversation / in-battle / travelling.
The owner asked for: regen + replace (done), **upload-your-own** (done, front-end), and **add new images with their
own prompts/scenarios, keeping the originals**. This brief is that last piece's engine half.

## 2. Current state (what constrains you)
- `forge/agents/art.py`: `FIXED_PORTRAIT_STATES = ("at-rest","in-conversation","in-battle","travelling")`.
  `build_prompt(character, state)` keys `STATE_ACT/STATE_CAM/STATE_ENV_PREFIX` on those 4; the **action beat** already
  honours `art.stateBeats[state]` if present (this is the hook to reuse). `generate_portrait` / `generate_portrait_set`
  save `output/portraits/<id>/<state>.png` and write `character.portraits[state] = {prompt,imageUrl,seed}`.
- `forge/web/app.py`: `POST /art`, `POST /art/set`, `GET /art/<id>/<state>.png` all **`abort(400/404)` when
  `state not in FIXED_PORTRAIT_STATES`** — this is the wall that blocks custom scenarios today.
- **INVARIANT (load-bearing):** `build_prompt` (engine) must equal the front-end `computePrompt()` byte-for-byte.
  The front-end ALSO reads `art.stateBeats[<key>]` — so if the custom scenario lives there as DATA, both sides agree.

## 3. The change (recommended design — DATA-carried, invariant-safe)
Treat a custom portrait as **a state with an arbitrary kebab key + its scenario carried in `art.stateBeats`**:
- A custom portrait has a `key` (e.g. `custom-tavern-brawl`), a `label` ("Tavern brawl"), and a `scenario`
  (the action text). Store the scenario as **`art.stateBeats[key] = scenario`** (DATA) — exactly the existing beat hook.
- `build_prompt(character, key)` for a custom key: use `art.stateBeats[key]` as the action, and a **generic cam +
  env** (reuse the at-rest cam/env, or a neutral default) so the prompt is fully determined by DATA. The front-end
  `computePrompt` mirrors this (build chat) → byte-for-byte holds because both read `art.stateBeats[key]` + the same
  generic cam/env fallback. **Agree the exact cam/env fallback string with the build chat so they match.**
- Keep the 4 fixed states 100% unchanged.

## 4. Endpoints — relax the state guard
- `POST /art` and `GET /art/<id>/<state>.png`: accept a custom `state` (validate it's a safe kebab slug, e.g.
  `^[a-z0-9-]{1,40}$`, NOT that it's in `FIXED_PORTRAIT_STATES`). The character carries the scenario in
  `art.stateBeats[state]`, so `build_prompt` already has what it needs.
- `POST /art/set`: leave it anchored on the FIXED four (the consistent SET is the four core states). Custom
  portraits are generated **one at a time via `/art`**, optionally `reference_image`-conditioned on the at-rest
  anchor for consistency (reuse the `input_fidelity:"high"` edit path).
- `generate_portrait`: drop the `state not in STATE_ACT` hard-raise; for unknown keys use the DATA beat + generic
  cam/env. Keep saving `portraits[key]` + the PNG.

## 5. Don't break
- The 4 fixed states, `generate_portrait_set`, and the set-conditioning (`input_fidelity`) must keep working.
- The byte-for-byte invariant — coordinate the custom cam/env fallback wording with the build chat.
- `tests/test_art.py` stays green; add a custom-key test (build_prompt for a custom key uses the beat; /art accepts it).

## 6. Front-end contract (build chat will wire — document, don't implement)
The Forge gets a **"+ Add scenario"**: the user types a label + scenario; the front-end picks a key
(`custom-<slug>`), sets `character.art.stateBeats[key] = scenario`, then `POST /art {id|character, state:key}`.
The result lands in `character.portraits[key]`. The Codex/Forge portrait cyclers iterate **all** keys
(`portraits` map) so customs appear alongside the four. Uploaded customs reuse the same `portraits[key]` slot
(embedded data-URI, already built front-end). Return the same `{prompt,imageUrl,seed}` slot shape as `/art`.

## 7. Definition of done
`POST /art` accepts a custom kebab `state` and generates from `art.stateBeats[state]`; the 4 fixed states +
`/art/set` + set-conditioning unchanged; `build_prompt` for a custom key is DATA-determined (so the build chat can
mirror it byte-for-byte); `tests/test_art.py` green + a custom-key test; nothing committed/pushed.
