#!/usr/bin/env python
"""Deterministic converter: CC-BY 2024 SRD monster markdown -> engine SRD JSON.

Source: https://github.com/downfallx/dnd-5e-srd-markdown @ 1b4b99dcb786cdd1a2fb26f8acec1551191f1ca4
        (SRD 5.2.1, (c) Wizards of the Coast LLC, CC-BY-4.0 -- see data/srd/2024/ATTRIBUTION.md)

5e-bits/5e-database ships only 3 of the SRD 5.2.1 monsters for 2024 (its conversion is
incomplete upstream), so the full set is built here from the CC-BY markdown instead -- the
same source already used for 2024 spells/levels by convert_srd2024_md.py.

Parses the two monster files into the SRD-2014 monster JSON shape that the engine /
front-end already consume (see data/srd/2014/5e-SRD-Monsters.json for the schema):

    monsters-A-Z.md + animals.md  ->  5e-SRD-Monsters.json  (~330 stat blocks)

Output keys mirror the 2014 monster object: index, name, size, type, subtype?, alignment,
armor_class, hit_points, hit_dice, hit_points_roll, speed, ability scores, proficiencies
(saves + skills), damage_{vulnerabilities,resistances,immunities}, condition_immunities,
senses, languages, challenge_rating, proficiency_bonus, xp, xp_in_lair?, special_abilities
(= Traits), actions, bonus_actions?, reactions?, legendary_actions?, image, url.

Action/trait entries carry the 2014 enrichment fields (attack_bonus / dc / damage / usage)
where they can be extracted with high confidence from the SRD text; the full description is
always preserved verbatim in `desc`.

Re-runnable: `.venv_forge/Scripts/python.exe scripts/convert_srd2024_monsters.py`.
"""
from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / ".srd2024_src"
OUT = ROOT / "data" / "srd" / "2024"
SOURCE_FILES = ("monsters-A-Z.md", "animals.md")

SIZES = ("Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan")
ABILS = ("str", "dex", "con", "int", "wis", "cha")
ABIL_FULL = {
    "Strength": "str", "Dexterity": "dex", "Constitution": "con",
    "Intelligence": "int", "Wisdom": "wis", "Charisma": "cha",
}
DAMAGE_TYPES = {
    "acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic",
    "piercing", "poison", "psychic", "radiant", "slashing", "thunder",
}
CONDITIONS = {
    "blinded", "charmed", "deafened", "exhaustion", "frightened", "grappled",
    "incapacitated", "invisible", "paralyzed", "petrified", "poisoned", "prone",
    "restrained", "stunned", "unconscious",
}
SUBSECTIONS = {
    "Traits": "special_abilities",
    "Actions": "actions",
    "Bonus Actions": "bonus_actions",
    "Reactions": "reactions",
    "Legendary Actions": "legendary_actions",
}

DESCRIPTOR = re.compile(
    r"^_(?P<size>(?:" + "|".join(SIZES) + r")(?: or (?:" + "|".join(SIZES) + r"))?)"
    r"\s+(?P<rest>.+?),\s+(?P<align>[A-Za-z][A-Za-z ]*)_\s*$"
)
HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
BOLD_FIELD = re.compile(r"^\*\*([A-Za-z][A-Za-z /]*?)\*\*\s*(.*)$")
ENTRY = re.compile(r"^\*\*_(?P<name>.+?)\.?_\*\*\s*(?P<rest>.*)$")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def _num(cell: str) -> int:
    cell = cell.strip().replace("−", "-").replace("–", "-").lstrip("+")
    if cell in ("", "—", "-", "–"):
        return 0
    try:
        return int(cell)
    except ValueError:
        return 0


def _clean(text: str) -> str:
    """Markdown stat-block prose -> plain text, line breaks preserved as '\\n'."""
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = text.replace("&emsp;", "").replace("&nbsp;", " ").replace("&ensp;", " ")
    text = re.sub(r"\*\*|\*|_", "", text)          # bold/italic markers
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


# --------------------------------------------------------------------------- ability table
class _AbilityTable(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell = []

    def handle_endtag(self, tag):
        if tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _parse_abilities(block: str) -> tuple[dict[str, int], dict[str, int]]:
    """Return ({abil: score}, {abil: save_total}) from the stat-block <table>."""
    m = re.search(r"<table>.*?</table>", block, re.DOTALL)
    scores: dict[str, int] = {}
    saves: dict[str, int] = {}
    if not m:
        return scores, saves
    p = _AbilityTable()
    p.feed(m.group(0))
    # body rows are those whose first cell is an ability label (STR/DEX/...)
    body = [r for r in p.rows if r and r[0].upper() in ("STR", "DEX", "CON", "INT", "WIS", "CHA")]
    for row in body:
        # each row holds three triples: LABEL score mod save | LABEL score mod save | ...
        for i in range(0, len(row), 4):
            chunk = row[i:i + 4]
            if len(chunk) < 4:
                continue
            ab = chunk[0].upper().lower()
            if ab not in ABILS:
                continue
            scores[ab] = _num(chunk[1])
            saves[ab] = _num(chunk[3])
    return scores, saves


# --------------------------------------------------------------------------- field parsers
def _parse_speed(val: str) -> dict[str, str]:
    speed: dict[str, str] = {}
    parts = [p.strip() for p in _clean(val).split(",") if p.strip()]
    for idx, part in enumerate(parts):
        m = re.match(r"^([A-Za-z]+)\s+(.*\bft\..*)$", part)
        if m and m.group(1).lower() in ("walk", "burrow", "climb", "fly", "swim"):
            speed[m.group(1).lower()] = m.group(2).strip()
        elif idx == 0:
            speed["walk"] = part
        else:
            # an unlabelled trailing clause (rare) -> attach to the previous value
            if speed:
                last = list(speed)[-1]
                speed[last] = f"{speed[last]}, {part}"
    return speed


def _parse_hp(val: str) -> tuple[int, str, str]:
    val = _clean(val)
    hp_m = re.match(r"^(\d+)", val)
    hp = int(hp_m.group(1)) if hp_m else 0
    dice = re.search(r"\(([^)]*)\)", val)
    hit_dice, hit_roll = "", ""
    if dice:
        dm = re.search(r"(\d+d\d+)(?:\s*([+\-])\s*(\d+))?", dice.group(1))
        if dm:
            hit_dice = dm.group(1)
            if dm.group(2):
                hit_roll = f"{dm.group(1)}{dm.group(2)}{dm.group(3)}"
            else:
                hit_roll = dm.group(1)
    return hp, hit_dice, hit_roll


def _parse_cr(val: str) -> tuple[float, int, int, int | None]:
    val = _clean(val)
    cr_m = re.match(r"^([0-9]+(?:/[0-9]+)?)", val)
    cr_raw = cr_m.group(1) if cr_m else "0"
    if "/" in cr_raw:
        a, b = cr_raw.split("/")
        cr: float = int(a) / int(b)
    else:
        cr = int(cr_raw)
    xp = 0
    xp_m = re.search(r"XP\s+([\d,]+)", val)
    if xp_m:
        xp = int(xp_m.group(1).replace(",", ""))
    lair_m = re.search(r"or\s+([\d,]+)\s+in lair", val)
    xp_lair = int(lair_m.group(1).replace(",", "")) if lair_m else None
    pb_m = re.search(r"PB\s+\+?(\d+)", val)
    pb = int(pb_m.group(1)) if pb_m else 2
    return cr, xp, pb, xp_lair


def _parse_senses(val: str) -> dict[str, object]:
    senses: dict[str, object] = {}
    for part in re.split(r"[;,]", _clean(val)):
        part = part.strip()
        if not part:
            continue
        pp = re.match(r"^Passive Perception\s+(\d+)", part, re.I)
        if pp:
            senses["passive_perception"] = int(pp.group(1))
            continue
        m = re.match(r"^([A-Za-z]+)\s+(.+)$", part)
        if m and m.group(1).lower() in ("darkvision", "blindsight", "tremorsense", "truesight"):
            senses[m.group(1).lower()] = m.group(2).strip()
    return senses


def _damage_list(val: str) -> list[str]:
    return [t.strip().lower() for t in re.split(r"[;,]", _clean(val)) if t.strip()]


def _parse_immunities(val: str) -> tuple[list[str], list[dict]]:
    dmg: list[str] = []
    cond: list[dict] = []
    for tok in re.split(r"[;,]", _clean(val)):
        tok = tok.strip()
        if not tok:
            continue
        low = tok.lower()
        if low in CONDITIONS:
            cond.append({
                "index": low, "name": tok.title() if low != tok else tok,
                "url": f"/api/2024/conditions/{low}",
            })
        else:
            dmg.append(low)
    return dmg, cond


# --------------------------------------------------------------------------- enrichment
def _dc(desc: str) -> dict | None:
    m = re.search(r"(" + "|".join(ABIL_FULL) + r")\s+Saving Throw:\s*DC\s*(\d+)", desc)
    if not m:
        return None
    ab = ABIL_FULL[m.group(1)]
    success = "none"
    tail = desc[m.end():]
    if re.search(r"Success:\s*Half|Half damage|takes half", tail, re.I):
        success = "half"
    return {
        "dc_type": {"index": ab, "name": ab.upper(), "url": f"/api/2024/ability-scores/{ab}"},
        "dc_value": int(m.group(2)),
        "success_type": success,
    }


def _attack_bonus(desc: str) -> int | None:
    m = re.search(r"(?:Melee|Ranged)(?:\s+or\s+Ranged)?\s+Attack Roll:\s*\+(\d+)", desc)
    return int(m.group(1)) if m else None


def _damage(desc: str) -> list[dict]:
    out: list[dict] = []
    for m in re.finditer(
        r"\d+\s*\((\d+d\d+(?:\s*[+\-]\s*\d+)?)\)\s+([A-Z][a-z]+)\s+damage", desc
    ):
        dtype = m.group(2).lower()
        if dtype not in DAMAGE_TYPES:
            continue
        dice = re.sub(r"\s+", "", m.group(1))
        out.append({
            "damage_type": {
                "index": dtype, "name": m.group(2),
                "url": f"/api/2024/damage-types/{dtype}",
            },
            "damage_dice": dice,
        })
    return out


def _usage(raw_name: str) -> tuple[str, dict | None]:
    """Split a trailing '(...)' usage clause off an entry name -> (clean_name, usage)."""
    m = re.search(r"\s*\((?P<u>[^)]*(?:Day|Recharge|Rest)[^)]*)\)\s*$", raw_name)
    if not m:
        return raw_name.strip(), None
    clause = m.group("u")
    name = raw_name[: m.start()].strip()
    usage: dict | None = None
    rech = re.search(r"Recharge\s+(\d+)(?:[–\-](\d+))?", clause)
    day = re.search(r"(\d+)/Day", clause)
    lair = re.search(r"(\d+)/Day in Lair", clause)
    if rech:
        usage = {"type": "recharge on roll", "dice": "1d6", "min_value": int(rech.group(1))}
    elif re.search(r"Recharge after .*Rest", clause, re.I):
        rest = []
        if re.search(r"short", clause, re.I):
            rest.append("short")
        if re.search(r"long", clause, re.I):
            rest.append("long")
        usage = {"type": "recharge after rest", "rest_types": rest or ["short", "long"]}
    elif day:
        usage = {"type": "per day", "times": int(day.group(1))}
        if lair:
            usage["times_in_lair"] = int(lair.group(1))
    return name, usage


# --------------------------------------------------------------------------- block parsing
def _split_paragraphs(text: str) -> list[str]:
    paras, cur = [], []
    for line in text.splitlines():
        if line.strip() == "":
            if cur:
                paras.append("\n".join(cur))
                cur = []
        else:
            cur.append(line)
    if cur:
        paras.append("\n".join(cur))
    return paras


def _parse_subsection(text: str) -> list[dict]:
    entries: list[dict] = []
    for para in _split_paragraphs(text):
        first = para.splitlines()[0].strip()
        em = ENTRY.match(first)
        if not em:
            continue  # skip <hr>, intro italics, stray prose
        raw_name = em.group("name").strip()
        name, usage = _usage(raw_name)
        rest_lines = [em.group("rest")] + para.splitlines()[1:]
        desc = _clean("\n".join(rest_lines))
        entry: dict = {"name": name, "desc": desc}
        ab = _attack_bonus(desc)
        if ab is not None:
            entry["attack_bonus"] = ab
        if usage:
            entry["usage"] = usage
        dc = _dc(desc)
        if dc:
            entry["dc"] = dc
        dmg = _damage(desc)
        if dmg:
            entry["damage"] = dmg
        entries.append(entry)
    return entries


def _type_from_rest(rest: str) -> tuple[str, str | None]:
    subtype = None
    sm = re.search(r"\(([^)]+)\)", rest)
    if sm:
        subtype = sm.group(1).strip().lower()
        rest = rest[: sm.start()].strip()
    if rest.lower().startswith("swarm of"):
        words = rest.split()
        words[0] = words[0].lower()           # Swarm -> swarm
        words[-1] = words[-1].lower()         # plural creature type -> lower
        mtype = " ".join(words)
    else:
        mtype = rest.strip().lower()
    return mtype, subtype


def parse_monster(name: str, block: str) -> dict | None:
    desc_m = None
    for line in block.splitlines():
        s = line.strip()
        if not s:
            continue
        desc_m = DESCRIPTOR.match(s)
        break
    if not desc_m:
        return None

    size = desc_m.group("size").split(" or ")[0]
    mtype, subtype = _type_from_rest(desc_m.group("rest"))
    alignment = desc_m.group("align").strip().lower()
    index = _slug(name)

    mon: dict = {"index": index, "name": name, "size": size, "type": mtype}
    if subtype:
        mon["subtype"] = subtype
    mon["alignment"] = alignment

    # split the block into the header (stat lines + table) and the named subsections
    head_lines: list[str] = []
    sub_order: list[tuple[str, list[str]]] = []
    cur_sub: list[str] | None = None
    for line in block.splitlines():
        hm = HEADING.match(line)
        if hm:
            title = hm.group(2).strip()
            key = SUBSECTIONS.get(title)
            if key:
                cur_sub = []
                sub_order.append((key, cur_sub))
                continue
            # a stat-block heading (the monster name) is not a subsection -> header text
        if cur_sub is None:
            head_lines.append(line)
        else:
            cur_sub.append(line)
    head = "\n".join(head_lines)

    fields: dict[str, str] = {}
    for line in head.splitlines():
        # a single line can carry two bold fields: "**AC** 17 **Initiative** +7 (17)"
        s = line.strip()
        bm = BOLD_FIELD.match(s)
        if bm:
            label = bm.group(1).strip()
            value = bm.group(2)
            value = re.split(r"\*\*[A-Za-z]", value)[0]  # cut a trailing 2nd field
            fields[label] = value.strip().rstrip("<br>").strip()

    ac_val = _num(re.match(r"\s*(\d+)", fields.get("AC", "0")).group(1)) if fields.get("AC") else 10
    mon["armor_class"] = [{"type": "natural", "value": ac_val}]

    hp, hit_dice, hit_roll = _parse_hp(fields.get("HP", ""))
    mon["hit_points"] = hp
    mon["hit_dice"] = hit_dice
    mon["hit_points_roll"] = hit_roll
    mon["speed"] = _parse_speed(fields.get("Speed", ""))

    scores, saves = _parse_abilities(block)
    for ab, full in (("str", "strength"), ("dex", "dexterity"), ("con", "constitution"),
                     ("int", "intelligence"), ("wis", "wisdom"), ("cha", "charisma")):
        mon[full] = scores.get(ab, 10)

    # proficiencies: saves (where save total != ability mod) + skills
    profs: list[dict] = []
    for ab in ABILS:
        if ab in scores and ab in saves:
            mod = (scores[ab] - 10) // 2
            if saves[ab] != mod:
                profs.append({
                    "value": saves[ab],
                    "proficiency": {
                        "index": f"saving-throw-{ab}",
                        "name": f"Saving Throw: {ab.upper()}",
                        "url": f"/api/2024/proficiencies/saving-throw-{ab}",
                    },
                })
    if fields.get("Skills"):
        for m in re.finditer(r"([A-Za-z][A-Za-z ]*?)\s*([+\-−]\d+)", _clean(fields["Skills"])):
            sk = m.group(1).strip()
            profs.append({
                "value": _num(m.group(2)),
                "proficiency": {
                    "index": f"skill-{_slug(sk)}",
                    "name": f"Skill: {sk}",
                    "url": f"/api/2024/proficiencies/skill-{_slug(sk)}",
                },
            })
    mon["proficiencies"] = profs

    mon["damage_vulnerabilities"] = _damage_list(fields["Vulnerabilities"]) if fields.get("Vulnerabilities") else []
    mon["damage_resistances"] = _damage_list(fields["Resistances"]) if fields.get("Resistances") else []
    if fields.get("Immunities"):
        dmg_imm, cond_imm = _parse_immunities(fields["Immunities"])
    else:
        dmg_imm, cond_imm = [], []
    mon["damage_immunities"] = dmg_imm
    mon["condition_immunities"] = cond_imm

    mon["senses"] = _parse_senses(fields.get("Senses", ""))
    # 2014 separates languages with commas; the SRD markdown uses ';' before "telepathy"
    mon["languages"] = _clean(fields.get("Languages", "")).replace("; ", ", ") or ""

    cr, xp, pb, xp_lair = _parse_cr(fields.get("CR", "0"))
    mon["challenge_rating"] = cr
    mon["proficiency_bonus"] = pb
    mon["xp"] = xp
    if xp_lair is not None:
        mon["xp_in_lair"] = xp_lair

    # subsections, in 2014 key order
    parsed_subs: dict[str, list[dict]] = {}
    for key, lines in sub_order:
        parsed_subs.setdefault(key, []).extend(_parse_subsection("\n".join(lines)))
    for key in ("special_abilities", "actions", "bonus_actions", "reactions", "legendary_actions"):
        if parsed_subs.get(key):
            mon[key] = parsed_subs[key]

    mon["image"] = f"/api/images/monsters/{index}.png"
    mon["url"] = f"/api/2024/monsters/{index}"
    return mon


def parse_file(text: str) -> list[dict]:
    lines = text.splitlines()
    # locate every heading that begins a stat block (next non-empty line is a descriptor)
    starts: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        hm = HEADING.match(line)
        if not hm:
            continue
        if SUBSECTIONS.get(hm.group(2).strip()):
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and DESCRIPTOR.match(lines[j].strip()):
            starts.append((i, hm.group(2).strip()))
    monsters: list[dict] = []
    for idx, (line_no, name) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        block = "\n".join(lines[line_no + 1:end])
        mon = parse_monster(name, block)
        if mon:
            monsters.append(mon)
    return monsters


def main() -> int:
    if not SRC.exists():
        print(f"ERROR: source clone not found at {SRC}", file=sys.stderr)
        print("Clone it first (see data/srd/2024/ATTRIBUTION.md).", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)

    all_monsters: list[dict] = []
    seen: dict[str, int] = {}
    for fn in SOURCE_FILES:
        path = SRC / fn
        if not path.exists():
            print(f"  WARN: missing {fn}", file=sys.stderr)
            continue
        parsed = parse_file(path.read_text(encoding="utf-8"))
        print(f"  {fn:<20} {len(parsed):>4} monsters")
        for mon in parsed:
            if mon["index"] in seen:
                continue  # first occurrence wins (animals never collide with A-Z)
            seen[mon["index"]] = 1
            all_monsters.append(mon)

    all_monsters.sort(key=lambda m: m["index"])
    out_path = OUT / "5e-SRD-Monsters.json"
    out_path.write_text(json.dumps(all_monsters, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Monsters: {len(all_monsters)} -> {out_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
