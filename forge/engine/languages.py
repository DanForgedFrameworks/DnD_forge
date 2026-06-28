"""Derive a PC/NPC's languages from canon + flavour, each with a description.

The ``languages`` field has historically been free text the forge AI typed. This turns it
into a sourced, described list:

- **Species** grants its tongues (Elf -> Common, Elvish) from the SRD, *except* when the
  species is a homebrew flavour grounded onto an SRD one (``pc.lineage`` set, e.g. a kender
  grounded to halfling) — then the SRD tongue (Halfling) is suppressed and the flavour tongue
  (Kenderspeak) is left for the AI/player to supply.
- **Class** grants secret tongues (rogue -> Thieves' Cant, druid -> Druidic) with their text.
- The AI's / player's own picks (Draconic, Sylvan, Auran, Kenderspeak…) are kept as ``chosen``.

Each entry is ``{name, source, description}``. Descriptions come from the SRD languages catalog
where known. Edition-aware.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from ..canon import SRDRepository

_HOMEBREW_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "srd" / "_homebrew"


@lru_cache(maxsize=4)
def _repo(edition: str = "2014") -> SRDRepository:
    return SRDRepository(edition)


@lru_cache(maxsize=1)
def _flavour_descriptions() -> dict:
    """Hand-authored flavour descriptions for languages (richer than the SRD catalog's terse
    script/speaker data), keyed by lower-cased name."""
    try:
        data = json.loads((_HOMEBREW_ROOT / "languages.json").read_text(encoding="utf-8"))
        return {k.lower(): v for k, v in data.items() if not k.startswith("_")}
    except Exception:
        return {}


# Classes that grant a secret language as a feature. These are routed HERE (to languages) and
# filtered out of the class-features list, so they appear once, as the tongue they are.
CLASS_LANGUAGES: dict[str, tuple[str, str]] = {
    "rogue": ("Thieves' Cant",
              "A secret mix of dialect, jargon, and code that lets you hide messages in "
              "seemingly normal conversation. Only another who knows Thieves' Cant understands."),
    "druid": ("Druidic",
              "The secret language of druids. You can speak it and use it to leave hidden "
              "messages; those who know Druidic automatically spot such a message, and others "
              "have little chance of noticing it."),
}
# names (lower-cased) that are class-granted languages — features.py drops these from its list
LANGUAGE_FEATURE_NAMES = {name.lower() for name, _ in CLASS_LANGUAGES.values()}


@lru_cache(maxsize=8)
def _lang_catalog(edition: str) -> dict:
    try:
        return {l.get("name", "").lower(): l for l in _repo(edition).all("languages")}
    except Exception:
        return {}


def _describe(edition: str, name: str) -> str:
    """Best available context for a language: a hand-authored flavour line first, else the SRD
    catalog's type/script/speakers, else "" (a bespoke flavour tongue the player describes)."""
    key = (name or "").lower()
    flavour = _flavour_descriptions().get(key)
    if flavour:
        return flavour
    e = _lang_catalog(edition).get(key)
    if not e:
        return ""
    bits = []
    if e.get("type"):
        bits.append(f"{e['type']} language")
    if e.get("script") and e["script"] != "None":
        bits.append(f"script: {e['script']}")
    speakers = e.get("typical_speakers") or []
    if speakers:
        bits.append("spoken by " + ", ".join(speakers))
    return " · ".join(bits)


def _class_mix(pc: dict) -> list[str]:
    classes = pc.get("classes")
    if isinstance(classes, list) and any((c or {}).get("class") for c in classes):
        return [(c.get("class") or "").lower() for c in classes if (c or {}).get("class")]
    return [(pc.get("class") or "").lower()]


_CLAUSE = re.compile(r"telepath|understand|can'?t speak|cannot|whistle|\bft\b|\bhp\b", re.I)


def _parse_existing(text: str) -> list[str]:
    """Pull clean language names out of a free-text languages line, dropping clauses like
    'telepathy 30 ft.' or 'understands Common but can't speak'."""
    out = []
    for part in re.split(r"[,;]", text or ""):
        p = part.strip().strip(".")
        if p and not _CLAUSE.search(p):
            out.append(p)
    return out


def derive_languages(character: dict, edition: str = "2014") -> list[dict]:
    """`[{name, source, description}]` — canon species + class tongues + the player's own picks,
    each with a flavour description. Suppresses the grounded-species tongue for a homebrew lineage
    (no 'Halfling' on a kender). Works for PCs and for NPCs that only carry a languages line.

    Manual/chosen languages persist in ``pc.extraLanguages`` (``[{name, description?}]``); a legacy
    character's chosen tongues are migrated there from its languages line on first derive, so the
    Studio editor and removals behave (the languages line itself is OUTPUT, not the source)."""
    pc = character.get("pc")
    has_pc = isinstance(pc, dict)
    pcd = pc if has_pc else {}
    species = (pcd.get("species") or "").lower()
    lineage = (pcd.get("lineage") or "").strip()
    grounded = bool(lineage) and lineage.lower() != species  # homebrew flavour grounded to SRD

    sp_entry = _repo(edition).get("species", species) or {} if species else {}
    sp_name = sp_entry.get("name") or species
    sp_langs = [l.get("name") for l in (sp_entry.get("languages") or []) if l.get("name")]
    suppress = {l.lower() for l in sp_langs if l.lower() != "common"} if grounded else set()

    out: list[dict] = []
    seen: set[str] = set()

    def add(name: str, source: str, desc: str | None = None):
        key = (name or "").strip().lower()
        if not key or key in seen or key in suppress:
            return
        seen.add(key)
        out.append({"name": name.strip(), "source": source,
                    "description": desc if desc else _describe(edition, name)})

    # 1) species tongues — Common always; the species language only when NOT a grounded flavour
    for ln in sp_langs:
        if ln.lower() == "common":
            add("Common", f"species:{sp_name}")
        elif not grounded:
            add(ln, f"species:{sp_name}")

    # 2) class secret tongues (rogue/druid)
    for ci in _class_mix(pcd):
        if ci in CLASS_LANGUAGES:
            nm, desc = CLASS_LANGUAGES[ci]
            add(nm, f"class:{ci.title()}", desc)

    auto = set(seen)  # everything so far is auto-granted by species/class

    # 3) the player's own picks. PCs persist them in pc.extraLanguages (migrating a legacy line
    #    once); NPCs with no pc keep using their languages line as the source.
    if has_pc:
        if "extraLanguages" not in pcd:
            migrated, seen_m = [], set()
            for ln in _parse_existing(character.get("languages") or ""):
                k = ln.lower()
                if k not in auto and k not in suppress and k not in seen_m:
                    seen_m.add(k)
                    migrated.append({"name": ln})
            pcd["extraLanguages"] = migrated
        manual = pcd.get("extraLanguages") or []
    else:
        manual = [{"name": ln} for ln in _parse_existing(character.get("languages") or "")]

    for el in manual:
        if isinstance(el, dict) and el.get("name"):
            add(el["name"], "chosen", el.get("description"))
        elif isinstance(el, str):
            add(el, "chosen")

    out.sort(key=lambda l: l["name"].lower() != "common")  # Common first, order otherwise stable
    return out


def languages_display(langs: list[dict]) -> str:
    """A clean comma-joined string for the statblock line, from the structured list."""
    return ", ".join(l["name"] for l in langs if l.get("name"))
