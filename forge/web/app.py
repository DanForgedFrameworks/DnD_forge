r"""The Flask bridge: the engine ↔ front-end meeting point.

Endpoints (all JSON unless noted), synchronous, permissive CORS for local dev:
  GET  /rulesets                  -> {rulesets:[{slug,label,extends}]}
  GET  /ruleset/<slug>            -> {slug,label,labels,abilityRules,statblock,optionLists}
  POST /forge {dump,ruleset?,kind?} -> {character, warnings:[{level,message}]}
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

from forge.agents import autofill, build_prompt, generate_portrait  # noqa: E402
from forge.agents.art import FIXED_PORTRAIT_STATES               # noqa: E402
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


# -- art ----------------------------------------------------------------------
@app.post("/art/preview")
def art_preview():
    body = request.get_json(force=True) or {}
    character = body.get("character") or {}
    state = body.get("state")
    if state not in FIXED_PORTRAIT_STATES:
        abort(400, f"state must be one of {FIXED_PORTRAIT_STATES}")
    return jsonify({"prompt": build_prompt(character, state)})


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

    try:
        slot = generate_portrait(character, state, adjustment=body.get("tweak"), seed=body.get("seed"))
    except Exception as e:  # surface backend/provider errors as JSON, not a 500 page
        return jsonify({"error": "image_generation_failed", "message": str(e)}), 502

    if from_store:  # persist the new portrait back onto the stored character
        (CHAR_DIR / f"{character['id']}.json").write_text(
            json.dumps(character, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return jsonify(slot)  # {prompt, imageUrl, seed}


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
        "accent": c.get("accent"),                # optional theme colour (pass-through)
        "ruleset": c.get("ruleset"), "level": (c.get("pc") or {}).get("level"),
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
    app.run(host="127.0.0.1", port=5000, debug=False)
