#!/usr/bin/env python
"""Import open-licensed third-party monsters (Kobold Press) into the engine's monster schema.

Source : Open5e API (https://open5e.com / https://api.open5e.com) -- a community aggregation of
         openly-licensed 5e content. We pull only the Kobold Press bestiary documents, all under the
         **Open Game License v1.0a (OGL 1.0a)**:
             tob-2023  Tome of Beasts (2023 revision)   (c) Open Design LLC
             tob2      Tome of Beasts 2                 (c) 2020 Open Design LLC
             tob3      Tome of Beasts 3                 (c) 2022 Open Design LLC
             cc        Creature Codex                   (c) 2018 Open Design LLC
         See data/expanded/ATTRIBUTION.md + data/expanded/OGL-1.0a.txt for the licence text and the
         full Section 15 copyright chain (OGL compliance).

This is THIRD-PARTY, NOT official WotC content. Every entry is tagged with a `source` block and
`"srd": false` so the engine/front-end can keep a clean "SRD only" mode and offer these as an
opt-in "include open content" overlay (tag & filter). They are written to data/expanded/monsters.json,
kept OUT of the SRD files on purpose.

Output mirrors the 2014 monster JSON shape (data/srd/2014/5e-SRD-Monsters.json) so the front-end
consumes it with the same code path. Re-runnable:
    .venv_forge/Scripts/python.exe scripts/import_open5e_monsters.py
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "expanded"
API = "https://api.open5e.com/v1/monsters/?document__slug={slug}&limit=500"

# the chosen Kobold Press OGL documents (publisher + short tag for unique indexes)
SOURCES = {
    "tob-2023": {"title": "Tome of Beasts", "publisher": "Kobold Press", "tag": "tob"},
    "tob2": {"title": "Tome of Beasts 2", "publisher": "Kobold Press", "tag": "tob2"},
    "tob3": {"title": "Tome of Beasts 3", "publisher": "Kobold Press", "tag": "tob3"},
    "cc": {"title": "Creature Codex", "publisher": "Kobold Press", "tag": "cc"},
}
LICENSE = "OGL-1.0a"

CONDITIONS = {
    "blinded", "charmed", "deafened", "exhaustion", "frightened", "grappled",
    "incapacitated", "invisible", "paralyzed", "petrified", "poisoned", "prone",
    "restrained", "stunned", "unconscious",
}
ABIL = {"strength": "str", "dexterity": "dex", "constitution": "con",
        "intelligence": "int", "wisdom": "wis", "charisma": "cha"}
# SRD challenge-rating -> XP and proficiency-bonus tables (derived, not in Open5e records)
CR_XP = {
    0: 10, 0.125: 25, 0.25: 50, 0.5: 100, 1: 200, 2: 450, 3: 700, 4: 1100, 5: 1800,
    6: 2300, 7: 2900, 8: 3900, 9: 5000, 10: 5900, 11: 7200, 12: 8400, 13: 10000,
    14: 11500, 15: 13000, 16: 15000, 17: 18000, 18: 20000, 19: 22000, 20: 25000,
    21: 33000, 22: 41000, 23: 50000, 24: 62000, 25: 75000, 26: 90000, 27: 105000,
    28: 120000, 29: 135000, 30: 155000,
}


def _get(url: str) -> dict:
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "dnd-character-forge"}), timeout=90).read())


def _fetch_all(slug: str) -> list[dict]:
    out, url = [], API.format(slug=slug)
    while url:
        page = _get(url)
        out.extend(page["results"])
        url = page.get("next")
    return out


def _pb_from_cr(cr: float) -> int:
    return 2 + (max(int(cr), 1) - 1) // 4


def _split_dice(hit_dice: str) -> tuple[str, str]:
    """'18d10+36' -> ('18d10', '18d10+36'); '7d8' -> ('7d8','7d8')."""
    hit_dice = (hit_dice or "").replace(" ", "")
    m = re.match(r"(\d+d\d+)", hit_dice)
    base = m.group(1) if m else hit_dice
    return base, hit_dice or base


def _speed(raw) -> dict:
    speed: dict[str, str] = {}
    if isinstance(raw, dict):
        hover = bool(raw.get("hover"))
        for k, v in raw.items():
            if k == "hover" or not isinstance(v, (int, float)):
                continue
            val = f"{int(v)} ft."
            if hover and k == "fly":
                val += " (hover)"
            speed[k] = val
    elif isinstance(raw, str) and raw.strip():
        speed["walk"] = raw.strip()
    return speed or {"walk": "0 ft."}


def _damage_list(s: str) -> list[str]:
    out: list[str] = []
    for clause in (s or "").split(";"):
        clause = clause.strip()
        if not clause:
            continue
        if re.search(r" from |\(| and ", clause):       # qualified phrase -> keep whole
            out.append(clause.lower())
        else:
            out.extend(t.strip().lower() for t in clause.split(",") if t.strip())
    return out


def _condition_immunities(s: str) -> list[dict]:
    out: list[dict] = []
    for tok in re.split(r"[;,]", s or ""):
        tok = tok.strip().lower()
        if tok in CONDITIONS:
            out.append({"index": tok, "name": tok.title(),
                        "url": f"/api/conditions/{tok}"})
    return out


def _senses(s: str) -> dict:
    senses: dict[str, object] = {}
    for part in re.split(r"[;,]", s or ""):
        part = part.strip()
        if not part:
            continue
        pp = re.match(r"passive Perception\s+(\d+)", part, re.I)
        if pp:
            senses["passive_perception"] = int(pp.group(1))
            continue
        m = re.match(r"([A-Za-z]+)\s+(.+)", part)
        if m and m.group(1).lower() in ("darkvision", "blindsight", "tremorsense", "truesight"):
            senses[m.group(1).lower()] = m.group(2).strip()
    return senses


def _proficiencies(mon: dict) -> list[dict]:
    profs: list[dict] = []
    for full, ab in ABIL.items():
        save = mon.get(f"{full}_save")
        if isinstance(save, int):
            profs.append({
                "value": save,
                "proficiency": {"index": f"saving-throw-{ab}", "name": f"Saving Throw: {ab.upper()}",
                                "url": f"/api/proficiencies/saving-throw-{ab}"},
            })
    skills = mon.get("skills") or {}
    if isinstance(skills, dict):
        for skill, val in skills.items():
            if not isinstance(val, int):
                continue
            label = skill.replace("_", " ").title()
            profs.append({
                "value": val,
                "proficiency": {"index": f"skill-{re.sub(r'[^a-z0-9]+', '-', skill.lower())}",
                                "name": f"Skill: {label}",
                                "url": f"/api/proficiencies/skill-{re.sub(r'[^a-z0-9]+', '-', skill.lower())}"},
            })
    return profs


# -- light action enrichment (Open5e uses 2014 phrasing) ----------------------
_DC = re.compile(r"DC\s*(\d+)\s+(Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma)\s+saving throw", re.I)
_ATK = re.compile(r"(?:Melee|Ranged|Melee or Ranged)\s+(?:Weapon|Spell)?\s*Attack:\s*\+(\d+)\s+to hit", re.I)
_DMG = re.compile(r"\d+\s*\((\d+d\d+(?:\s*[+\-]\s*\d+)?)\)\s+([A-Za-z]+)\s+damage")
_DMG_TYPES = {"acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic",
              "piercing", "poison", "psychic", "radiant", "slashing", "thunder"}


def _enrich(desc: str) -> dict:
    extra: dict = {}
    a = _ATK.search(desc or "")
    if a:
        extra["attack_bonus"] = int(a.group(1))
    d = _DC.search(desc or "")
    if d:
        ab = d.group(2)[:3].lower()
        success = "half" if re.search(r"half", desc[d.end():], re.I) else "none"
        extra["dc"] = {"dc_type": {"index": ab, "name": ab.upper(),
                                   "url": f"/api/ability-scores/{ab}"},
                       "dc_value": int(d.group(1)), "success_type": success}
    dmg = []
    for m in _DMG.finditer(desc or ""):
        t = m.group(2).lower()
        if t in _DMG_TYPES:
            dmg.append({"damage_type": {"index": t, "name": m.group(2).title(),
                                        "url": f"/api/damage-types/{t}"},
                        "damage_dice": re.sub(r"\s+", "", m.group(1))})
    if dmg:
        extra["damage"] = dmg
    return extra


def _entries(raw) -> list[dict]:
    out: list[dict] = []
    for a in (raw or []):
        if not isinstance(a, dict) or not a.get("name"):
            continue
        desc = (a.get("desc") or "").strip()
        entry = {"name": a["name"].strip(), "desc": desc}
        entry.update(_enrich(desc))
        out.append(entry)
    return out


def convert(mon: dict, src_slug: str) -> dict:
    src = SOURCES[src_slug]
    cr = float(mon.get("cr", mon.get("challenge_rating", 0)) or 0)
    cr_val = int(cr) if cr == int(cr) else cr
    hit_dice, hit_roll = _split_dice(mon.get("hit_dice", ""))
    ac_type = (mon.get("armor_desc") or "natural").strip() or "natural"

    out: dict = {
        "index": f"{src['tag']}-{mon['slug']}",
        "name": mon["name"],
        "size": (mon.get("size") or "Medium").strip(),
        "type": (mon.get("type") or "").strip().lower(),
    }
    if (mon.get("subtype") or "").strip():
        out["subtype"] = mon["subtype"].strip().lower()
    out["alignment"] = (mon.get("alignment") or "unaligned").strip().lower()
    out["armor_class"] = [{"type": ac_type, "value": int(mon.get("armor_class") or 10)}]
    out["hit_points"] = int(mon.get("hit_points") or 0)
    out["hit_dice"] = hit_dice
    out["hit_points_roll"] = hit_roll
    out["speed"] = _speed(mon.get("speed"))
    for full, ab in ABIL.items():
        out[full] = int(mon.get(full) or 10)
    out["proficiencies"] = _proficiencies(mon)
    out["damage_vulnerabilities"] = _damage_list(mon.get("damage_vulnerabilities"))
    out["damage_resistances"] = _damage_list(mon.get("damage_resistances"))
    out["damage_immunities"] = _damage_list(mon.get("damage_immunities"))
    out["condition_immunities"] = _condition_immunities(mon.get("condition_immunities"))
    out["senses"] = _senses(mon.get("senses"))
    out["languages"] = (mon.get("languages") or "").strip()
    out["challenge_rating"] = cr_val
    out["proficiency_bonus"] = _pb_from_cr(cr)
    out["xp"] = CR_XP.get(cr if cr in CR_XP else cr_val, 0)
    if _entries(mon.get("special_abilities")):
        out["special_abilities"] = _entries(mon.get("special_abilities"))
    if _entries(mon.get("actions")):
        out["actions"] = _entries(mon.get("actions"))
    if _entries(mon.get("bonus_actions")):
        out["bonus_actions"] = _entries(mon.get("bonus_actions"))
    if _entries(mon.get("reactions")):
        out["reactions"] = _entries(mon.get("reactions"))
    if _entries(mon.get("legendary_actions")):
        out["legendary_actions"] = _entries(mon.get("legendary_actions"))
    out["image"] = mon.get("img_main") or None
    # provenance for tag & filter
    out["srd"] = False
    out["source"] = {
        "name": src["title"], "publisher": src["publisher"], "slug": src_slug,
        "license": LICENSE, "url": "https://open5e.com",
    }
    out["url"] = f"https://open5e.com/monsters/{mon['slug']}"
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    all_mon: list[dict] = []
    seen: set[str] = set()
    for slug in SOURCES:
        try:
            raw = _fetch_all(slug)
        except Exception as e:                       # pragma: no cover
            print(f"  ERROR fetching {slug}: {e}", file=sys.stderr)
            return 1
        kept = 0
        for mon in raw:
            if not mon.get("slug") or not mon.get("name"):
                continue
            obj = convert(mon, slug)
            if obj["index"] in seen:
                continue
            seen.add(obj["index"])
            all_mon.append(obj)
            kept += 1
        print(f"  {SOURCES[slug]['title']:<22} {kept:>4} monsters")
    all_mon.sort(key=lambda m: m["index"])
    out_path = OUT / "monsters.json"
    out_path.write_text(json.dumps(all_mon, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Open5e monsters: {len(all_mon)} -> {out_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
