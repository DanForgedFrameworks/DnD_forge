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

FIXED_TAIL = (
    "full-body fantasy character art, cinematic composition, consistent character "
    "design across the set, rich detail, dramatic natural light"
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
    segments.append(_clean(art.get("style")) or "painterly high fantasy")
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
) -> dict:
    if state not in STATE_ACT:
        raise ValueError(f"unknown state {state!r}")
    prompt = build_prompt(character, state, adjustment=adjustment)
    backend = backend or _default_backend()
    result = backend(prompt, seed)

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


# 1x1 transparent PNG — lets the stub exercise the real save+URL path with no API.
_STUB_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def stub_backend(prompt: str, seed: int | None = None) -> dict:
    token = seed if seed is not None else int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
    return {"image_bytes": _STUB_PNG, "seed": token}


def _aspect_from_size(size: str) -> str:
    try:
        w, h = (int(x) for x in str(size).lower().split("x"))
    except Exception:
        return "1:1"
    if w == h:
        return "1:1"
    return "16:9" if w > h else "9:16"


def gemini_backend(prompt: str, seed: int | None = None) -> dict:
    """Generate a portrait with Google Imagen (google-genai) and return PNG bytes.

    NOTE: the Gemini Developer API has no image seed (Vertex-only), so the returned
    `seed` is a deterministic prompt token for round-tripping, not pixel reproduction.
    """
    import os

    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set (put it in .env)")

    cfg = _image_config()
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_images(
        model=cfg.get("model", "imagen-4.0-generate-001"),
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio=_aspect_from_size(cfg.get("size", "1024x1024")),
        ),
    )
    images = getattr(resp, "generated_images", None) or []
    if not images:
        raise RuntimeError("Imagen returned no images (the prompt may have been filtered)")

    token = seed if seed is not None else int(
        hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16
    )
    return {"image_bytes": images[0].image.image_bytes, "seed": token}


def gemini_flash_backend(prompt: str, seed: int | None = None) -> dict:
    """Generate a portrait with Gemini 2.5 Flash Image ('nano banana') via generate_content.

    Free-tier accessible (unlike Imagen). Same `seed`-is-a-token caveat: the Developer API
    doesn't expose an image seed, so `seed` is for round-tripping only.
    """
    import os

    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set (put it in .env)")

    cfg = _image_config()
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=cfg.get("flashModel", "gemini-2.5-flash-image"),
        contents=[prompt],
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
    )

    data = None
    for cand in (getattr(resp, "candidates", None) or []):
        content = getattr(cand, "content", None)
        for part in (getattr(content, "parts", None) or []):
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                data = inline.data
                break
        if data:
            break
    if not data:
        raise RuntimeError("Gemini Flash returned no image (possibly filtered or text-only)")
    if isinstance(data, str):  # some SDK paths return base64 text
        data = base64.b64decode(data)

    token = seed if seed is not None else int(
        hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16
    )
    return {"image_bytes": data, "seed": token}


_BACKENDS = {"stub": stub_backend, "gemini": gemini_backend, "gemini-flash": gemini_flash_backend}


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
