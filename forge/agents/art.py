"""Prompt C — portrait pipeline: deterministic prompt assembly + image generation.

`build_prompt(character, state)` reproduces the front-end prototype's `computePrompt()`
byte-for-byte (authoritative spec) so the previewed prompt equals the generated one.
Pure, no API, no randomness.

`generate_portrait(character, state)` builds the prompt, calls a pluggable image backend
(raw bytes), saves the PNG, and writes
`character.portraits[state] = {prompt, imageUrl, seed}` where imageUrl is a usable
<img src> URL served by the Flask app at /art/{id}/{state}.png.

camelCase aliases `buildPrompt` / `generatePortrait` match the contract's named API.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path

FIXED_PORTRAIT_STATES = ("at-rest", "in-conversation", "in-battle", "travelling")

# kebab key -> sentence-case label. The variant suffix lowercases it.
STATE_LABELS = {
    "at-rest": "At rest",
    "in-conversation": "In conversation",
    "in-battle": "In battle",
    "travelling": "Travelling",
}

# Per-state scene triple (authoritative — matches computePrompt()).
# action = generic act unless overridden by art.stateBeats[state]; cam is ALWAYS the
# generic one (set consistency); envPrefix reframes the environment clause per state.
STATE_ACT = {
    "at-rest": "calm and at ease in a quiet, unguarded moment, relaxed candid posture",
    "in-conversation": "mid-conversation, expressive and gesturing toward a companion just off-frame",
    "in-battle": "in the thick of combat, caught mid-action with real weight and motion",
    "travelling": "on the move and mid-stride, covering ground",
}
STATE_CAM = {
    "at-rest": "intimate close framing, soft warm ambient light",
    "in-conversation": "eye-level medium shot, warm even daylight",
    "in-battle": "dramatic low angle, harsh rim light, dust and embers, high tension",
    "travelling": "wide establishing shot, big sky and shifting weather, long golden-hour light",
}
STATE_ENV_PREFIX = {
    "at-rest": "in a sheltered, still corner of",
    "in-conversation": "in a lived-in, occupied part of",
    "in-battle": "amid the chaos and wreckage of",
    "travelling": "crossing the open expanse of",
}

KIND_WORDS = {
    "monster": "monster",
    "npc": "NPC",
    "creature": "creature",
    "companion": "animal companion",
    "pet": "pet familiar",
    "character": "hero adventurer",
}

# The locked house ART STYLE — used ONLY when the character has no custom `art.style`. A custom
# art.style REPLACES this (per-character style control), so e.g. a cartoonish look isn't fought by
# "gritty painterly". MUST stay byte-for-byte identical to computePrompt()'s house-style fallback.
HOUSE_STYLE = (
    "in the style of Greg Rutkowski and Tyler Jacobson, gritty painterly high-fantasy "
    "digital illustration, dramatic cinematic lighting"
)
# Technical/quality + no-text constraints — ALWAYS appended, whatever the style. Keeps full-body
# framing, set consistency and the no-text rule even for a custom style.
FIXED_TAIL = (
    "full-body fantasy character art, cinematic composition, consistent character design across "
    "the set, rich detail, absolutely no text, lettering, words, captions, speech bubbles, numbers, "
    "signage or writing of any kind anywhere in the image"
)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG = _REPO_ROOT / "config" / "forge_config.json"
_ART_DIR = _REPO_ROOT / "output" / "portraits"


def _clean(s: str | None) -> str:
    """trim, then strip a single trailing period (matches the front-end clean())."""
    t = (s or "").strip()
    return t[:-1] if t.endswith(".") else t


def _title(s: str | None) -> str:
    """Title-case each alphabetic run, preserving separators ('high-elf' -> 'High-Elf')."""
    return re.sub(r"[A-Za-z]+", lambda m: m.group(0).capitalize(), s or "")


# -- prompt assembly (pure, deterministic, matches computePrompt) -------------
def build_prompt(
    character: dict, state: str, *, adjustment: str | None = None, include_cues: bool = False
) -> str:
    if state not in STATE_ACT:
        raise ValueError(f"unknown state {state!r}; expected one of {tuple(STATE_ACT)}")

    art = character.get("art") or {}
    size = (character.get("size") or "").strip()
    ctype = (character.get("type") or "").strip()
    kind = (character.get("kind") or "creature").strip()
    name = character.get("name") or ""
    pc = character.get("pc") or {}

    segments: list[str] = []

    # 1) subject — PC override pulls from pc{}, else size+type statblock framing
    if kind == "character" and pc.get("class"):
        sp = pc.get("subspecies") or pc.get("species") or ""
        subject = f"a Dungeons & Dragons player character, a {_title(sp)} {_title(pc['class'])}"
        if pc.get("subclass"):
            subject += f" ({_title(pc['subclass'])})"
    else:
        kind_word = KIND_WORDS.get(kind, kind)
        prefix = f"{size} {ctype} — " if (size or ctype) else ""
        subject = f"{prefix}a Dungeons & Dragons {kind_word}"
    if name:
        subject += f" named “{name}”"
    segments.append(subject)

    # 2) appearance / outfit / pose (each only if present)
    if art.get("appearance"):
        segments.append(_clean(art["appearance"]))
    if art.get("outfit"):
        segments.append("wearing " + _clean(art["outfit"]))
    if art.get("pose"):
        segments.append("characteristic pose: " + _clean(art["pose"]))

    # 3) scene = "{action}; {cam}" (cam always the generic per-state cam)
    beats = (art.get("stateBeats") or {}).get(state)
    action = _clean(beats) if beats else STATE_ACT[state]
    segments.append(f"{action}; {STATE_CAM[state]}")

    # 4) environment, reframed per state via envPrefix
    env = art.get("environment")
    if env:
        segments.append(f"{STATE_ENV_PREFIX[state]} {_clean(env)}, a high-fantasy world")
    else:
        segments.append(f"{STATE_ENV_PREFIX[state]} an evocative high-fantasy location")

    # 5) mood, 6) style, 7) fixed tail
    if art.get("personality"):
        segments.append("mood: " + _clean(art["personality"]))
    # style: the character's own art.style REPLACES the house style; else the locked house style
    segments.append(_clean(art.get("style")) or HOUSE_STYLE)
    segments.append(FIXED_TAIL)

    base = "“" + ". ".join(segments) + ". — " + STATE_LABELS[state].lower() + " variant.”"

    # opt-in trailing additions (kept OUTSIDE the quote so the base stays byte-identical
    # to computePrompt). Off by default → engine output == front-end preview, zero delta.
    extras: list[str] = []
    if include_cues:
        cue = _statblock_cues(character, state)
        if cue:
            extras.append(cue)
    if adjustment:
        extras.append(f"Adjustment: {_clean(adjustment)}")
    return base + ("".join(f" {e}" for e in extras))


def _statblock_cues(character: dict, state: str) -> str:
    """Optional, opt-in visual motifs from the statblock (flying -> airborne, etc.)."""
    cues: list[str] = []
    speed = (character.get("speed") or "").lower()
    if "fly" in speed or "hover" in speed:
        cues.append(
            "airborne with wings spread, catching the light"
            if state in ("in-battle", "travelling")
            else "hovering just above the ground"
        )
    resist = (character.get("resist") or "").lower()
    for dmg, motif in (
        ("fire", "embers and heat-glow"), ("cold", "frost and pale vapour"),
        ("lightning", "crackling arcs of energy"), ("psychic", "a faint eerie violet aura"),
        ("poison", "a sickly green haze"), ("radiant", "a soft holy radiance"),
        ("necrotic", "wisps of dark decay"),
    ):
        if dmg in resist:
            cues.append(motif)
            break
    if not cues:
        return ""
    s = ", ".join(cues)
    return s[0].upper() + s[1:] + "."


# -- image generation (pluggable backend returning raw bytes) -----------------
def generate_portrait(
    character: dict,
    state: str,
    *,
    adjustment: str | None = None,
    seed: int | None = None,
    backend=None,
    reference_image: bytes | None = None,
    master_image: bytes | None = None,
    prompt_override: str | None = None,
) -> dict:
    """Build the prompt, call the backend, save the PNG, write the portraits slot.

    `reference_image` (optional) is forwarded to the backend so the generated image
    can be conditioned on an anchor portrait (same character/face/gender). The `openai`
    backend honours it (via images.edit); `stub` accepts and ignores it.
    `master_image` (optional) — the OWNER's portrait, forwarded so a creature's master
    appears as a small background figure resembling the real owner (Option 2).

    `prompt_override` (optional) — when a non-empty string is supplied, it is used
    VERBATIM as the prompt instead of `build_prompt(...)`. This powers the front-end
    "edit this prompt" feature; the byte-for-byte build_prompt==computePrompt invariant
    still holds whenever no override is given (the default).
    """
    if state not in STATE_ACT:
        raise ValueError(f"unknown state {state!r}")
    override = (prompt_override or "").strip()
    prompt = override if override else build_prompt(character, state, adjustment=adjustment)
    backend = backend or _default_backend()
    result = backend(prompt, seed, reference_image=reference_image, master_image=master_image)

    cid = character.get("id") or "creature"
    out_dir = _ART_DIR / cid
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{state}.png").write_bytes(result["image_bytes"])

    base_url = _image_config().get("base_url", "http://localhost:5000").rstrip("/")
    image_url = f"{base_url}/art/{cid}/{state}.png"

    portraits = character.setdefault(
        "portraits",
        {s: {"prompt": None, "imageUrl": None, "seed": None} for s in FIXED_PORTRAIT_STATES},
    )
    portraits[state] = {"prompt": prompt, "imageUrl": image_url, "seed": result["seed"]}
    return portraits[state]


def generate_portrait_set(
    character: dict,
    *,
    anchor_state: str = "at-rest",
    anchor_image: bytes | None = None,
    seed: int | None = None,
    backend=None,
    prompt_overrides: dict | None = None,
    master_image: bytes | None = None,
) -> dict:
    """Generate the four-state portrait SET as one consistent character (Item 6).

    One anchor image is produced first (or supplied), then the other three states are
    generated *conditioned on the anchor's PNG bytes* so they depict the same person —
    same face/build/gender — fixing the per-state drift of independent generation.

    Steps:
      1. Lock the appearance (incl. gender) and class beats onto the character DATA so
         every prompt in the set agrees (idempotent; also done at forge time).
      2. If `anchor_image` is None, generate `anchor_state` normally and read its PNG
         bytes back; else use the supplied bytes (regenerate-from-chosen-anchor path).
      3. Generate the other three states with `reference_image=<anchor bytes>`.

    Returns the full `{state: slot}` map. Backend-pluggable (tests pass `stub`).
    """
    if anchor_state not in STATE_ACT:
        raise ValueError(f"unknown anchor_state {anchor_state!r}; expected one of {tuple(STATE_ACT)}")
    backend = backend or _default_backend()

    # appearance + gender + companion + class beats live as DATA (keeps build_prompt == computePrompt)
    lock_appearance(character)
    apply_companion(character)
    apply_class_beats(character)

    ov = {k: v for k, v in (prompt_overrides or {}).items() if (v or "").strip()}

    cid = character.get("id") or "creature"
    if anchor_image is None:
        generate_portrait(character, anchor_state, seed=seed, backend=backend, prompt_override=ov.get(anchor_state), master_image=master_image)
        anchor_image = (_ART_DIR / cid / f"{anchor_state}.png").read_bytes()
    else:
        # caller supplied the chosen anchor's bytes — persist it as the anchor slot too,
        # so a fresh set is self-consistent even if the anchor wasn't generated here.
        out_dir = _ART_DIR / cid
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{anchor_state}.png").write_bytes(anchor_image)
        base_url = _image_config().get("base_url", "http://localhost:5000").rstrip("/")
        portraits = character.setdefault(
            "portraits",
            {s: {"prompt": None, "imageUrl": None, "seed": None} for s in FIXED_PORTRAIT_STATES},
        )
        portraits[anchor_state] = {
            "prompt": ov.get(anchor_state, "").strip() or build_prompt(character, anchor_state),
            "imageUrl": f"{base_url}/art/{cid}/{anchor_state}.png",
            "seed": seed,
        }

    for state in FIXED_PORTRAIT_STATES:
        if state == anchor_state:
            continue
        generate_portrait(character, state, seed=seed, backend=backend, reference_image=anchor_image, prompt_override=ov.get(state), master_image=master_image)

    return {s: character["portraits"][s] for s in FIXED_PORTRAIT_STATES}


# -- forge-time enrichment: appearance/gender lock (Item 6) + class beats (Item 7) ----
# These write DATA onto character.art so build_prompt (== computePrompt) stays byte-for-
# byte identical — no prose logic moves into build_prompt, no front-end edit needed.

# canonical gender tokens -> normalised value (whole-word matched; pronouns count)
_GENDER_CANON = {
    "male": "male", "man": "male", "men": "male", "masculine": "male", "boy": "male",
    "he": "male", "him": "male", "his": "male",
    "female": "female", "woman": "female", "women": "female", "feminine": "female",
    "girl": "female", "she": "female", "her": "female", "hers": "female",
    "nonbinary": "nonbinary", "non-binary": "nonbinary", "enby": "nonbinary",
    "agender": "nonbinary", "genderless": "nonbinary", "they": "nonbinary", "them": "nonbinary",
    "androgynous": "androgynous", "ambiguous": "androgynous",
}
# normalised gender -> explicit, non-wandering clause prepended to the appearance prose
_GENDER_CLAUSE = {
    "male": "male-presenting",
    "female": "female-presenting",
    "nonbinary": "androgynous, nonbinary-presenting",
    "androgynous": "androgynous",
}


def _normalise_gender(value: str | None) -> str:
    """First gender-bearing whole word in `value` -> normalised gender ('' if none)."""
    for word in re.findall(r"[a-z][a-z-]*", (value or "").lower()):
        if word in _GENDER_CANON:
            return _GENDER_CANON[word]
    return ""


def lock_appearance(character: dict) -> dict:
    """Ensure `art.appearance` carries an explicit, stable gender so the SET agrees (Item 6).

    Deterministic and idempotent. Runs in the forge path (after auto-fill) and again at the
    top of `generate_portrait_set`. Order of precedence for the gender:
      1. an explicit `art.gender` authored by the auto-fill agent,
      2. a gender word/pronoun already in `art.appearance`,
      3. for player characters only, a stable `androgynous` default (enforces presence so
         the face can't wander; creatures with no gender signal are left untouched).
    When a gender is settled and not already stated in the prose, it is prepended to
    `art.appearance` as an explicit clause. Returns the (mutated) `art` dict.
    """
    art = character.setdefault("art", {})
    appearance = (art.get("appearance") or "").strip()
    detected = _normalise_gender(art.get("gender")) or _normalise_gender(appearance)
    is_pc = character.get("kind") == "character"
    gender = detected or ("androgynous" if is_pc else "")
    if gender:
        art["gender"] = gender
        if not _normalise_gender(appearance):  # not already conveyed by the prose
            clause = _GENDER_CLAUSE[gender]
            art["appearance"] = f"{clause}, {appearance}" if appearance else clause
    return art


# Per-class scene beat per state (Item 7). Lowercase action fragments matching STATE_ACT's
# style; build_prompt joins them as the {action} clause. Keyed by SRD class index / role.
# in-conversation beats always read as ACTIVELY TALKING (mid-conversation, speaking AND
# gesturing toward someone) so the state is unmistakable. Beats never conjure an animal
# companion — a real companion rides in via `art.companion` (apply_companion) so it appears
# consistently across ALL four states, not just at-rest.
CLASS_STATE_BEATS = {
    "rogue": {
        "at-rest": "lounging in shadow, idly turning a dagger, watchful and unhurried",
        "in-conversation": "mid-conversation, leaning in with a sly half-smile, speaking low and conspiratorially, gesturing toward someone just off-frame",
        "in-battle": "striking from the shadows, blade reversed for a precise, lethal jab",
        "travelling": "moving low and silent along the margins, scanning for trouble",
    },
    "wizard": {
        "at-rest": "poring over an open spellbook by candlelight, deep in study",
        "in-conversation": "mid-conversation, speaking and gesturing thoughtfully toward someone just off-frame as faint arcane motes drift from the fingertips",
        "in-battle": "mid-incantation, hands wreathed in crackling arcane energy",
        "travelling": "walking staff in hand, a soft conjured light bobbing alongside",
    },
    "barbarian": {
        "at-rest": "seated by a fire sharpening a great weapon, coiled and restless",
        "in-conversation": "mid-conversation, speaking with blunt force toward someone just off-frame, jaw set, gesturing emphatically",
        "in-battle": "roaring mid-rage, muscles straining, swinging a massive weapon",
        "travelling": "striding hard over rough ground, weapon slung across the shoulders",
    },
    "cleric": {
        "at-rest": "in quiet prayer, a holy symbol cradled in both hands, serene",
        "in-conversation": "mid-conversation, offering counsel aloud toward someone just off-frame, a calm steady gaze and an open, gesturing hand",
        "in-battle": "raising a holy symbol high, divine radiance blazing outward",
        "travelling": "walking with measured purpose, holy symbol catching the light",
    },
    "fighter": {
        "at-rest": "at ease but alert, checking the edge of a well-kept blade",
        "in-conversation": "mid-conversation, speaking plainly and attentively toward someone just off-frame, gesturing with one hand, the other resting on the pommel",
        "in-battle": "braced behind a shield, driving forward with disciplined precision",
        "travelling": "marching steadily in full kit, eyes on the road ahead",
    },
    "ranger": {
        "at-rest": "crouched at a campsite, tending gear and checking arrows, watchful",
        "in-conversation": "mid-conversation, speaking and gesturing toward someone just off-frame, watchful even while talking",
        "in-battle": "loosing an arrow mid-stride, already reaching for the next",
        "travelling": "tracking a trail through wilderness, bow in hand, alert to every sign",
    },
    "bard": {
        "at-rest": "idly strumming an instrument, relaxed and amused",
        "in-conversation": "mid-conversation, performing the moment, speaking expressively and gesturing toward someone just off-frame, drawing every eye",
        "in-battle": "weaving a flourish of inspiring magic mid-duel, blade and song together",
        "travelling": "ambling along humming a tune, an instrument slung across the back",
    },
    "paladin": {
        "at-rest": "kneeling in solemn vigil, hands resting on a sheathed sword",
        "in-conversation": "mid-conversation, speaking with earnest conviction toward someone just off-frame, upright and gesturing resolutely",
        "in-battle": "smiting forward, weapon blazing with righteous radiant light",
        "travelling": "riding tall and watchful, armour gleaming, banner-straight posture",
    },
    "sorcerer": {
        "at-rest": "raw magic flickering unbidden across the fingertips, restless",
        "in-conversation": "mid-conversation, speaking animatedly toward someone just off-frame, sparks of innate power dancing as they gesture",
        "in-battle": "unleashing a torrent of raw elemental sorcery, hair and cloak whipping",
        "travelling": "walking wrapped in a faint shimmer of barely-contained power",
    },
    "warlock": {
        "at-rest": "brooding in dim light, eldritch sigils glimmering faintly nearby",
        "in-conversation": "mid-conversation, speaking with quiet menace toward someone just off-frame, gesturing as an otherworldly patron's presence is felt",
        "in-battle": "hurling crackling eldritch blasts, eyes alight with otherworldly power",
        "travelling": "moving through gloom, pact weapon manifest and shadows clinging close",
    },
    "druid": {
        "at-rest": "seated among growing things, at ease in the wild",
        "in-conversation": "mid-conversation, speaking slowly and earthily toward someone just off-frame, gesturing as leaves and pollen drift past",
        "in-battle": "mid-transformation, nature magic surging, the form blurring toward a beast",
        "travelling": "moving easily through wilderness, the land seeming to part in welcome",
    },
    "monk": {
        "at-rest": "seated in flawless meditation, perfectly still and centred",
        "in-conversation": "mid-conversation, speaking with quiet precision toward someone just off-frame, economical gestures",
        "in-battle": "mid flurry of blows, body flowing through a precise martial form",
        "travelling": "moving with light, balanced, tireless grace over any terrain",
    },
}


def _character_role(character: dict) -> str:
    """The class/role used to pick beats: PC class index, else a top-level `role`."""
    pc = character.get("pc") or {}
    return (pc.get("class") or character.get("role") or "").strip().lower()


def apply_class_beats(character: dict) -> dict:
    """Fill `art.stateBeats` from the character's class/role (Item 7), unless already set.

    Deterministic. Runs in the forge path so the class-specific action beats live in
    character DATA — `build_prompt` already reads `art.stateBeats`, so the front-end
    preview (`computePrompt`) stays byte-for-byte identical with no front-end change.
    A character whose `art.stateBeats` is already populated (user/agent-authored) is left
    untouched; a class with no mapped beats is a no-op. Returns the (mutated) `art` dict.
    """
    art = character.setdefault("art", {})
    if art.get("stateBeats"):  # user/agent already authored beats — never overwrite
        return art
    beats = CLASS_STATE_BEATS.get(_character_role(character))
    if beats:
        art["stateBeats"] = dict(beats)
    return art


def apply_companion(character: dict) -> dict:
    """Carry a pet/animal companion into EVERY state's prompt, not just at-rest.

    `art.companion` is a non-rendered DATA field (free text, e.g. "a large grey wolf").
    build_prompt does NOT read it directly (that would diverge from computePrompt); instead
    this helper weaves it into `art.appearance` — an existing rendered field both
    build_prompt and computePrompt read — so the companion appears *alongside* the character
    consistently across at-rest / in-conversation / in-battle / travelling. Deterministic and
    idempotent (won't double-append). No-op when `art.companion` is unset. Returns `art`.
    """
    art = character.setdefault("art", {})
    companion = (art.get("companion") or "").strip()
    if not companion:
        return art
    appearance = (art.get("appearance") or "").strip()
    if companion.lower() not in appearance.lower():  # not already woven in
        phrase = f"accompanied by {companion} always at their side"
        art["appearance"] = f"{appearance}, {phrase}" if appearance else phrase
    return art


# 1x1 transparent PNG — lets the stub exercise the real save+URL path with no API.
_STUB_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def stub_backend(prompt: str, seed: int | None = None, *, reference_image: bytes | None = None, master_image: bytes | None = None) -> dict:
    # reference_image / master_image accepted but ignored — conditioning requires the openai backend.
    token = seed if seed is not None else int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
    return {"image_bytes": _STUB_PNG, "seed": token}


def openai_backend(prompt: str, seed: int | None = None, *, reference_image: bytes | None = None, master_image: bytes | None = None) -> dict:
    """Generate a portrait with OpenAI's image model (gpt-image-*) and return PNG bytes.

    Renders the SAME locked house-style prompt (Rutkowski/Tyler-Jacobson) as the other
    backends — only the engine differs, for a like-for-like style comparison.

    Reference images (all optional) drive `images.edit`; with none, `images.generate` is used:
      - `reference_image` — the subject's own anchor PNG, to keep the SAME character across the
        four-state SET (Item 6).
      - `master_image` — the OWNER's portrait (Image-Fidelity Option 2): the creature's master is
        rendered as a small, distant background figure RESEMBLING that person. Combines with
        `reference_image` (two-subject edit) or stands alone (fresh anchor).

    Config (`config/forge_config.json` "image"): `openaiModel` (default "gpt-image-1"),
    `openaiSize` (default "1024x1024"). If the configured model id is unavailable on the
    account, it falls back to "gpt-image-1". Same `seed`-is-a-token caveat as the others.
    """
    import io
    import os

    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set (put it in .env)")

    cfg = _image_config()
    size = cfg.get("openaiSize", "1024x1024")
    models = [cfg.get("openaiModel", "gpt-image-1")]
    if "gpt-image-1" not in models:  # documented, always-available fallback
        models.append("gpt-image-1")
    client = OpenAI(api_key=api_key)

    # input_fidelity="high" tells the edit endpoint to PRESERVE the anchor's face/build/outfit
    # (the main lever for a consistent SET); falls back gracefully if the API rejects the param.
    cfg_fidelity = cfg.get("openaiInputFidelity", "high")

    # Assemble the reference-image list + matching edit instruction.
    refs: list = []
    instruction = ""
    if reference_image is not None and master_image is not None:
        instruction = (
            "Image 1 is the MAIN subject — keep that character IDENTICAL (face, build, gender, "
            "hair, colouring, outfit); change only pose, action, framing, lighting and environment. "
            "Image 2 is the subject's master/owner: render a SMALL, DISTANT background figure that "
            "RESEMBLES the person in image 2 (their face, build and colouring), kept far behind and "
            "minor — NOT a second main subject. Scene: "
        )
        a = io.BytesIO(reference_image); a.name = "subject.png"
        b = io.BytesIO(master_image); b.name = "master.png"
        refs = [a, b]
    elif master_image is not None:
        instruction = (
            "Render the subject described below. The reference image is the subject's master/owner: "
            "include a SMALL, DISTANT background figure that RESEMBLES the person in the reference image "
            "(face, build and colouring), kept far behind and minor — NOT a second main subject. Scene: "
        )
        b = io.BytesIO(master_image); b.name = "master.png"
        refs = [b]
    elif reference_image is not None:
        instruction = (
            "Keep the SAME character as the reference image — identical face, build, gender, "
            "hair, colouring, and outfit; change only the pose, action, framing, lighting, and "
            "environment to match this scene: "
        )
        a = io.BytesIO(reference_image); a.name = "anchor.png"
        refs = [a]
    use_edit = len(refs) > 0

    if use_edit:
        def call(m, with_fidelity):
            for r in refs:
                r.seek(0)
            kw = dict(model=m, image=(refs if len(refs) > 1 else refs[0]), prompt=instruction + prompt, size=size)
            if with_fidelity and cfg_fidelity:
                kw["input_fidelity"] = cfg_fidelity
            return client.images.edit(**kw)
    else:
        def call(m, with_fidelity):
            return client.images.generate(model=m, prompt=prompt, size=size)

    last_err = None
    resp = None
    for m in models:
        # edit path: try WITH input_fidelity first, then WITHOUT (older-API compatibility)
        for with_fidelity in ((True, False) if use_edit else (False,)):
            try:
                resp = call(m, with_fidelity)
                break
            except Exception as e:
                last_err = e
                continue
        if resp is not None:
            break
    if resp is None:
        raise RuntimeError(f"OpenAI image generation failed: {last_err}")

    b64 = resp.data[0].b64_json
    data = base64.b64decode(b64)
    token = seed if seed is not None else int(
        hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16
    )
    return {"image_bytes": data, "seed": token}


_BACKENDS = {
    "stub": stub_backend,
    "openai": openai_backend,
}


def _image_config() -> dict:
    try:
        return json.loads(_CONFIG.read_text(encoding="utf-8")).get("image", {})
    except Exception:
        return {}


def _default_backend():
    provider = _image_config().get("provider", "stub")
    if provider in _BACKENDS:
        return _BACKENDS[provider]
    raise NotImplementedError(f"image provider {provider!r} not wired (available: {list(_BACKENDS)})")


# camelCase aliases to match the contract's named API
buildPrompt = build_prompt
generatePortrait = generate_portrait
generatePortraitSet = generate_portrait_set
lockAppearance = lock_appearance
applyClassBeats = apply_class_beats
applyCompanion = apply_companion
