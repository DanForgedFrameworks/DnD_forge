r"""The Flask bridge: the engine ↔ front-end meeting point.

Endpoints (all JSON unless noted), synchronous, permissive CORS for local dev:
  GET  /rulesets                  -> {rulesets:[{slug,label,extends}]}
  GET  /ruleset/<slug>            -> {slug,label,labels,abilityRules,statblock,optionLists}
  POST /forge {dump,ruleset?,kind?} -> {character, warnings:[{level,message}]}
  POST /forge/sheet (multipart: file, ruleset?, kind?, rulesMode?) -> {character, warnings}
  POST /art/preview {character,state} -> {prompt}
  POST /art {id?|character?,state,tweak?,seed?} -> {imageUrl,seed,prompt}
  GET  /character                 -> {characters:[{id,name,kind,ruleset,level}]}
  GET  /character/<id>            -> Character (404 if missing)
  POST /character {character}     -> {id, character}   (apply_derived + save; id = slug)
  GET  /art/<id>/<state>.png      -> image/png bytes (404 if not generated)

Run from the repo root:  .venv_forge\Scripts\python -m forge.web.app
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:  # ensure .env (API keys) is loaded for this process
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env")
except Exception:
    pass

from flask import Flask, jsonify, request, send_file, abort  # noqa: E402

from forge.agents import autofill, build_prompt, generate_portrait, generate_portrait_set  # noqa: E402
from forge.agents.art import FIXED_PORTRAIT_STATES               # noqa: E402
from forge.agents.sheet_extract import (                         # noqa: E402
    extract_sheet_text, UnsupportedSheetType,
)
from forge.contract import apply_derived                          # noqa: E402
from forge.engine import resolve_pc_proficiencies                 # noqa: E402
from forge.ruleset import Ruleset                                 # noqa: E402
from forge.web.forge_log import log_forge                         # noqa: E402

CHAR_DIR = _REPO_ROOT / "output" / "characters"
TRASH_DIR = CHAR_DIR / "_trash"          # soft-deleted characters (recoverable)
PORTRAIT_DIR = _REPO_ROOT / "output" / "portraits"
RULESET_DIR = _REPO_ROOT / "config" / "rulesets"

app = Flask(__name__)


@app.after_request
def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


def _slug(name: str | None) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "creature").lower()).strip("-")
    return s or "creature"


# -- rulesets -----------------------------------------------------------------
@app.get("/rulesets")
def list_rulesets():
    out = []
    for p in sorted(RULESET_DIR.glob("*.json")):
        try:
            cfg = json.loads(p.read_text(encoding="utf-8"))
            out.append({"slug": cfg.get("slug", p.stem), "label": cfg.get("label"), "extends": cfg.get("extends")})
        except Exception:
            continue
    return jsonify({"rulesets": out})


@app.get("/ruleset/<slug>")
def get_ruleset(slug):
    rs = Ruleset(slug)  # unknown slug falls back to dnd5e-2014 inside the loader
    return jsonify({
        "slug": rs.slug,
        "label": rs.label,
        "labels": rs.labels,
        "abilityRules": rs.ability_rules,
        "statblock": rs.statblock,
        "optionLists": rs.option_lists(),
    })


@app.get("/spells")
def spells_for_class():
    """The SRD spell list a class can take at a level, + the legal counts (for the picker).

    Query: class (index, required), level (int), ruleset (slug), and the six ability scores
    (str/dex/con/int/wis/cha) so the prepared-count can use the right casting-ability mod.
    Returns {spells: [{index,name,level}], limits: {cantrips,leveled,maxSpellLevel,casterType,
    ability} | null, edition}. Advisory only — the front-end never blocks on these.
    """
    from forge.engine import rules_mode as rm

    cls = (request.args.get("class") or "").strip().lower()
    if not cls:
        abort(400, "`class` is required")
    try:
        level = int(request.args.get("level", "1"))
    except (TypeError, ValueError):
        level = 1
    try:
        edition = Ruleset(request.args.get("ruleset", "dnd5e-2014")).config.get("srdEdition", "2014")
    except Exception:
        edition = "2014"

    abilities = {}
    for k in ("str", "dex", "con", "int", "wis", "cha"):
        v = request.args.get(k)
        if v is not None:
            try:
                abilities[k] = int(v)
            except (TypeError, ValueError):
                pass
    rules = rm.CASTER_RULES.get(cls)
    ability_mod = 0
    if rules and abilities.get(rules["ability"]) is not None:
        ability_mod = (abilities[rules["ability"]] - 10) // 2

    return jsonify({
        "spells": rm.class_spells_detailed(cls, edition),
        "limits": rm.spell_limits(cls, level, ability_mod, edition),
        "edition": edition,
    })


# -- forge (brain-dump -> character) ------------------------------------------
@app.post("/forge")
def forge():
    body = request.get_json(force=True) or {}
    started = time.time()
    try:
        result = autofill(
            body.get("dump", ""),
            ruleset=body.get("ruleset", "dnd5e-2014"),
            kind=body.get("kind"),
            rules_mode=body.get("rulesMode", "relaxed"),   # strict | relaxed (PC only)
            details=body.get("details"),                   # optional Forge flavour notes (PC)
        )
    except Exception as e:  # log the failure too, then surface it as JSON (not a 500 page)
        log_forge(body, None, started=started, error=repr(e))
        return jsonify({"error": "forge_failed", "message": str(e)}), 502
    log_forge(body, result, started=started)
    return jsonify(result)  # {character, warnings:[{level,message}]}


# -- forge from an existing sheet (upload .docx/.pdf/.txt -> character) --------
@app.post("/forge/sheet")
def forge_sheet():
    """Upload an existing character sheet; extract its text; run the auto-fill agent.

    multipart/form-data: `file` (required) + optional `ruleset`, `kind` (default
    "character" — a sheet is almost always a PC), `rulesMode` (default "relaxed").
    Returns the SAME {character, warnings:[{level,message}]} shape as /forge, so the
    front-end reuses its existing "land the draft in the Studio" logic.
    """
    upload = request.files.get("file")
    if upload is None or not (upload.filename or "").strip():
        return jsonify({"error": "no_file", "message": "Attach a file in the `file` field."}), 400

    ruleset = request.form.get("ruleset", "dnd5e-2014")
    kind = request.form.get("kind", "character")
    rules_mode = request.form.get("rulesMode", "relaxed")

    started = time.time()
    # request_body mirrors /forge's log shape so the same forge_log record is produced.
    log_body = {"dump": f"[sheet upload: {upload.filename}]", "ruleset": ruleset,
                "kind": kind, "rulesMode": rules_mode}
    try:
        text = extract_sheet_text(upload.filename, upload.read())
    except UnsupportedSheetType as e:
        return jsonify({"error": "unsupported_type", "message": str(e)}), 400
    except Exception as e:  # a corrupt/unreadable file shouldn't 500
        log_forge(log_body, None, started=started, error=repr(e))
        return jsonify({"error": "extract_failed", "message": str(e)}), 422

    if not text:
        return jsonify({"error": "no_text",
                        "message": "Couldn't read text from that file (a scanned image PDF?)."}), 422

    try:
        result = autofill("", ruleset=ruleset, kind=kind, rules_mode=rules_mode, docx_text=text)
    except Exception as e:  # surface provider errors as JSON 502, not a 500 page
        log_forge(log_body, None, started=started, error=repr(e))
        return jsonify({"error": "forge_failed", "message": str(e)}), 502
    log_forge(log_body, result, started=started)
    return jsonify(result)  # {character, warnings:[{level,message}]}


# -- art ----------------------------------------------------------------------
@app.post("/art/preview")
def art_preview():
    body = request.get_json(force=True) or {}
    character = body.get("character") or {}
    state = body.get("state")
    if state not in FIXED_PORTRAIT_STATES:
        abort(400, f"state must be one of {FIXED_PORTRAIT_STATES}")
    return jsonify({"prompt": build_prompt(character, state)})


def _master_image_for(character: dict) -> bytes | None:
    """Owner's at-rest portrait bytes for a bonded creature (Image-Fidelity Option 2), or None.

    Resolved from `companionOf.id` (the owner's character id) — no request param needed. Returns
    None when the character has no owner, or the owner has no at-rest portrait on disk yet. Lets a
    creature's master be rendered as a small background figure resembling the real owner.
    """
    co = character.get("companionOf") or {}
    owner_id = co.get("id")
    if not owner_id:
        return None
    p = PORTRAIT_DIR / str(owner_id) / "at-rest.png"
    return p.read_bytes() if p.exists() else None


@app.post("/art")
def art_generate():
    body = request.get_json(force=True) or {}
    state = body.get("state")
    if state not in FIXED_PORTRAIT_STATES:
        abort(400, f"state must be one of {FIXED_PORTRAIT_STATES}")

    character = body.get("character")
    from_store = False
    if character is None:
        cid = body.get("id")
        path = CHAR_DIR / f"{cid}.json"
        if not cid or not path.exists():
            abort(404, "provide `character`, or an `id` of a saved character")
        character = json.loads(path.read_text(encoding="utf-8"))
        from_store = True
    character.setdefault("id", _slug(character.get("name")))

    # Root a single-state regenerate to the at-rest anchor (same face/build/outfit across the set),
    # mirroring /art/set. Skips when regenerating the anchor itself, or when no anchor exists yet,
    # or when the caller opts out (anchor=false, e.g. a deliberate fresh take).
    anchor_image = None
    if state != "at-rest" and body.get("anchor", True):
        anchor_path = PORTRAIT_DIR / character["id"] / "at-rest.png"
        if anchor_path.exists():
            anchor_image = anchor_path.read_bytes()

    # Image-Fidelity Option 2: render the owner as a small background figure resembling the real
    # owner (resolved from companionOf). Opt out with `master:false`.
    master_image = _master_image_for(character) if body.get("master", True) else None

    try:
        slot = generate_portrait(
            character, state, adjustment=body.get("tweak"), seed=body.get("seed"),
            prompt_override=body.get("promptOverride"), reference_image=anchor_image,
            master_image=master_image,
        )
    except Exception as e:  # surface backend/provider errors as JSON, not a 500 page
        return jsonify({"error": "image_generation_failed", "message": str(e)}), 502

    if from_store:  # persist the new portrait back onto the stored character
        (CHAR_DIR / f"{character['id']}.json").write_text(
            json.dumps(character, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return jsonify(slot)  # {prompt, imageUrl, seed}


@app.post("/art/set")
def art_generate_set():
    """Generate the four-state portrait SET as one consistent character (Item 6).

    Body: {id?|character?, anchorState?="at-rest", seed?}. The anchor is generated first
    (or, for the regenerate-from-chosen-anchor flow, an already-generated anchor PNG on
    disk is reused as-is), then the other three states are conditioned on the anchor's
    bytes so they depict the same person. Mirrors /art's from-store persistence + JSON
    error handling. Returns {"portraits": {state: slot}} for all four states.
    """
    body = request.get_json(force=True) or {}
    anchor_state = body.get("anchorState", "at-rest")
    if anchor_state not in FIXED_PORTRAIT_STATES:
        abort(400, f"anchorState must be one of {FIXED_PORTRAIT_STATES}")

    character = body.get("character")
    from_store = False
    if character is None:
        cid = body.get("id")
        path = CHAR_DIR / f"{cid}.json"
        if not cid or not path.exists():
            abort(404, "provide `character`, or an `id` of a saved character")
        character = json.loads(path.read_text(encoding="utf-8"))
        from_store = True
    character.setdefault("id", _slug(character.get("name")))

    # Regenerate-with-chosen-anchor: if the chosen anchor state already has a PNG on disk,
    # reuse it as the anchor (don't regenerate it); otherwise generate it fresh.
    anchor_path = PORTRAIT_DIR / character["id"] / f"{anchor_state}.png"
    anchor_image = anchor_path.read_bytes() if anchor_path.exists() else None

    master_image = _master_image_for(character) if body.get("master", True) else None

    try:
        portraits = generate_portrait_set(
            character, anchor_state=anchor_state, anchor_image=anchor_image, seed=body.get("seed"),
            prompt_overrides=body.get("promptOverrides"), master_image=master_image,
        )
    except Exception as e:  # surface backend/provider errors as JSON, not a 500 page
        return jsonify({"error": "image_generation_failed", "message": str(e)}), 502

    if from_store:  # persist the new portrait set back onto the stored character
        (CHAR_DIR / f"{character['id']}.json").write_text(
            json.dumps(character, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return jsonify({"portraits": portraits})


@app.get("/art/<cid>/<state>.png")
def serve_portrait(cid, state):
    if state not in FIXED_PORTRAIT_STATES:
        abort(404)
    path = PORTRAIT_DIR / cid / f"{state}.png"
    if not path.exists():
        abort(404)
    return send_file(path, mimetype="image/png")


# -- characters ---------------------------------------------------------------
def _char_summary(c: dict, stem: str) -> dict:
    return {
        "id": c.get("id", stem), "name": c.get("name"), "kind": c.get("kind"),
        "challenge": c.get("challenge"),          # rail shows CR / level
        "hp": c.get("hp"), "ac": c.get("ac"),     # Party tab quick-stats
        "accent": c.get("accent"),                # optional theme colour (pass-through)
        "ruleset": c.get("ruleset"), "level": (c.get("pc") or {}).get("level"),
        "companionOf": c.get("companionOf"),      # link: a forged companion/pet/familiar's owner
        "bondType": c.get("bondType"),            # "Familiar" | "Companion" | "Pet" — lets the library split Familiars out
    }


def _list_summaries(directory: Path) -> list:
    directory.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(directory.glob("*.json")):
        try:
            out.append(_char_summary(json.loads(p.read_text(encoding="utf-8")), p.stem))
        except Exception:
            continue
    return out


@app.get("/character")
def list_characters():
    return jsonify({"characters": _list_summaries(CHAR_DIR)})  # _trash is a subdir, excluded


@app.get("/trash")
def list_trash():
    return jsonify({"characters": _list_summaries(TRASH_DIR)})


@app.get("/character/<cid>")
def get_character(cid):
    path = CHAR_DIR / f"{cid}.json"
    if not path.exists():
        abort(404)
    return jsonify(json.loads(path.read_text(encoding="utf-8")))


@app.delete("/character/<cid>")
def delete_character(cid):
    """Soft-delete: move the character into _trash (recoverable). Portraits stay put."""
    import shutil

    path = CHAR_DIR / f"{cid}.json"
    if not path.exists():
        abort(404)
    TRASH_DIR.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(TRASH_DIR / f"{cid}.json"))
    return jsonify({"trashed": cid})


@app.post("/trash/<cid>/restore")
def restore_character(cid):
    import shutil

    src = TRASH_DIR / f"{cid}.json"
    if not src.exists():
        abort(404)
    CHAR_DIR.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(CHAR_DIR / f"{cid}.json"))
    return jsonify({"restored": cid})


@app.delete("/trash/<cid>")
def purge_character(cid):
    """Permanent delete from the trash, including the generated portraits."""
    import shutil

    src = TRASH_DIR / f"{cid}.json"
    if src.exists():
        src.unlink()
    shutil.rmtree(PORTRAIT_DIR / cid, ignore_errors=True)
    return jsonify({"purged": cid})


@app.post("/character")
def save_character():
    body = request.get_json(force=True) or {}
    character = body.get("character") or body
    character["id"] = character.get("id") or _slug(character.get("name"))
    resolve_pc_proficiencies(character)  # PC: derive saveProfs/skillProfs/proficiencies from class+bg
    apply_derived(character)  # keep saves/skills/senses + spell DC/attack consistent on disk
    CHAR_DIR.mkdir(parents=True, exist_ok=True)
    (CHAR_DIR / f"{character['id']}.json").write_text(
        json.dumps(character, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return jsonify({"id": character["id"], "character": character})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("FORGE_PORT", "5000")), debug=False)
