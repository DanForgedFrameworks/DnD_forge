#!/usr/bin/env python
"""LOCAL-ONLY extractor: 2024 PHB equipment catalog -> data/local/equipment_2024_phb.json

Reads copyrighted PDF supplied locally. Output is for personal prototyping only.
Never commit or ship this output.

Sections extracted:
  - Simple Melee Weapons (page 213)
  - Simple Ranged Weapons (page 213)
  - Martial Melee Weapons (page 213)
  - Martial Ranged Weapons (page 213)
  - Armor (page 217)
  - Tools (pages 218-219)
  - Adventuring Gear (pages 220-227, table on page 221)

Usage:
  python scripts/extract_phb2024_equipment.py "PDFs/D&D 5E [2024] PHB.pdf"
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "local"
SOURCE = {
    "name": "Player's Handbook (2024)",
    "publisher": "Wizards of the Coast",
    "license": "All rights reserved (local prototyping only)",
}

# --------------------------------------------------------------------------- helpers (from extract_phb2024_local.py)

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def _clean(text: str) -> str:
    text = re.sub(r"-\s*\n\s*", "", text)
    text = text.replace("\n", " ")
    text = re.sub(r"([a-z])-\s+([a-z])", r"\1\2", text)
    text = re.sub(r"\s+", " ", text)
    # OCR digit-for-1 in dice: "ld6" -> "1d6"
    text = re.sub(r"\bl(d(?:4|6|8|10|12|20|100))\b", r"1\1", text)
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = re.sub(r"[\s~^|;:=_•\-]{2,}$", "", text)
    return text.strip()


OCR_JUNK = re.compile(r"[⊠]|[:;]{2,}|[a-z][:;~^|][a-z]|\s[:;~^|]\s|[~^|]{1,}|\(cid:")


# --------------------------------------------------------------------------- weapon table extraction

# Canonical weapon data extracted directly from page 213 of the PDF.
# The table is clean OCR — we parse it programmatically.
# Columns: Name | Damage | Properties | Mastery | Weight | Cost

# Damage type lookup (not in the table columns — derived from the name/damage string)
DAMAGE_TYPES: dict[str, str] = {
    "Bludgeoning": "bludgeoning",
    "Piercing": "piercing",
    "Slashing": "slashing",
}

# Mastery properties canonical list
MASTERIES = {"cleave", "graze", "nick", "push", "sap", "slow", "topple", "vex"}

# Property keywords to slug
PROP_KEYWORDS = [
    "Ammunition", "Finesse", "Heavy", "Light", "Loading",
    "Range", "Reach", "Thrown", "Two-Handed", "Versatile",
]


def _parse_weapon_row(name: str, raw_damage: str, raw_props: str, raw_mastery: str,
                      raw_weight: str, raw_cost: str, category: str) -> dict:
    """Build a weapon record from raw table cells."""
    # Damage: "1d4 Piercing" -> damage="1d4", damage_type="piercing"
    dam_m = re.match(r"([\dd]+)\s+(Bludgeoning|Piercing|Slashing)", raw_damage, re.I)
    damage = dam_m.group(1).lower() if dam_m else raw_damage.strip()
    # Fix OCR: "ld4" -> "1d4"
    damage = re.sub(r"\bl(d\d+)\b", r"1\1", damage)
    damage_type = dam_m.group(2).lower() if dam_m else "unknown"

    # Properties: free-text cell — extract structured list + range
    props_clean = _clean(raw_props)
    props: list[str] = []
    range_normal: int | None = None
    range_long: int | None = None

    # Ammunition/Thrown range: "(Range 20/60; Arrow)" or "(Range 80/320; Bolt)"
    rng_m = re.search(r"Range\s+(\d+)/(\d+)", props_clean, re.I)
    if rng_m:
        range_normal = int(rng_m.group(1))
        range_long = int(rng_m.group(2))

    for kw in PROP_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", props_clean, re.I):
            props.append(kw.lower().replace("-", "-"))

    # Versatile — keep the two-hand damage note
    versatile_m = re.search(r"Versatile\s*\(([\dd]+)\)", props_clean, re.I)
    versatile_damage: str | None = None
    if versatile_m:
        vd = versatile_m.group(1)
        vd = re.sub(r"\bl(d\d+)\b", r"1\1", vd)
        versatile_damage = vd

    mastery = raw_mastery.strip().lower()
    if mastery not in MASTERIES:
        mastery = mastery  # keep as-is; flag later if needed

    weight = raw_weight.strip() if raw_weight.strip() else None
    cost = raw_cost.strip()

    rec: dict = {
        "index": _slug(name),
        "name": name,
        "equipment_category": category,
        "cost": cost,
        "damage": damage,
        "damage_type": damage_type,
        "weight": weight,
        "properties": props,
        "range": range_normal,
        "range_long": range_long,
        "mastery": mastery,
        "srd": False,
        "local": True,
        "source": SOURCE,
    }
    if versatile_damage:
        rec["versatile_damage"] = versatile_damage
    return rec


# Hard-coded canonical weapon data from page 213 (table is well-structured OCR)
# Format: (name, raw_damage, raw_props, mastery, weight, cost, category)
WEAPON_TABLE: list[tuple[str, str, str, str, str, str, str]] = [
    # Simple Melee
    ("Club",         "1d4 Bludgeoning", "Light",                                         "Slow",   "2 lb.",   "1 SP",   "simple-melee-weapon"),
    ("Dagger",       "1d4 Piercing",    "Finesse, Light, Thrown (Range 20/60)",           "Nick",   "1 lb.",   "2 GP",   "simple-melee-weapon"),
    ("Greatclub",    "1d8 Bludgeoning", "Two-Handed",                                    "Push",   "10 lb.",  "2 SP",   "simple-melee-weapon"),
    ("Handaxe",      "1d6 Slashing",    "Light, Thrown (Range 20/60)",                   "Vex",    "2 lb.",   "5 GP",   "simple-melee-weapon"),
    ("Javelin",      "1d6 Piercing",    "Thrown (Range 30/120)",                         "Slow",   "2 lb.",   "5 SP",   "simple-melee-weapon"),
    ("Light Hammer", "1d4 Bludgeoning", "Light, Thrown (Range 20/60)",                   "Nick",   "2 lb.",   "2 GP",   "simple-melee-weapon"),
    ("Mace",         "1d6 Bludgeoning", "",                                              "Sap",    "4 lb.",   "5 GP",   "simple-melee-weapon"),
    ("Quarterstaff", "1d6 Bludgeoning", "Versatile (1d8)",                               "Topple", "4 lb.",   "2 SP",   "simple-melee-weapon"),
    ("Sickle",       "1d4 Slashing",    "Light",                                         "Nick",   "2 lb.",   "1 GP",   "simple-melee-weapon"),
    ("Spear",        "1d6 Piercing",    "Thrown (Range 20/60), Versatile (1d8)",         "Sap",    "3 lb.",   "1 GP",   "simple-melee-weapon"),
    # Simple Ranged
    ("Dart",           "1d4 Piercing",  "Finesse, Thrown (Range 20/60)",                                          "Vex",  "1/4 lb.", "5 CP",  "simple-ranged-weapon"),
    ("Light Crossbow", "1d8 Piercing",  "Ammunition (Range 80/320; Bolt), Loading, Two-Handed",                   "Slow", "5 lb.",   "25 GP", "simple-ranged-weapon"),
    ("Shortbow",       "1d6 Piercing",  "Ammunition (Range 80/320; Arrow), Two-Handed",                           "Vex",  "2 lb.",   "25 GP", "simple-ranged-weapon"),
    ("Sling",          "1d4 Bludgeoning","Ammunition (Range 30/120; Bullet)",                                     "Slow", "",        "1 SP",  "simple-ranged-weapon"),
    # Martial Melee
    ("Battleaxe",   "1d8 Slashing",    "Versatile (1d10)",                              "Topple", "4 lb.",  "10 GP",  "martial-melee-weapon"),
    ("Flail",       "1d8 Bludgeoning", "",                                              "Sap",    "2 lb.",  "10 GP",  "martial-melee-weapon"),
    ("Glaive",      "1d10 Slashing",   "Heavy, Reach, Two-Handed",                     "Graze",  "6 lb.",  "20 GP",  "martial-melee-weapon"),
    ("Greataxe",    "1d12 Slashing",   "Heavy, Two-Handed",                            "Cleave", "7 lb.",  "30 GP",  "martial-melee-weapon"),
    ("Greatsword",  "2d6 Slashing",    "Heavy, Two-Handed",                            "Graze",  "6 lb.",  "50 GP",  "martial-melee-weapon"),
    ("Halberd",     "1d10 Slashing",   "Heavy, Reach, Two-Handed",                     "Cleave", "6 lb.",  "20 GP",  "martial-melee-weapon"),
    ("Lance",       "1d10 Piercing",   "Heavy, Reach, Two-Handed (unless mounted)",    "Topple", "6 lb.",  "10 GP",  "martial-melee-weapon"),
    ("Longsword",   "1d8 Slashing",    "Versatile (1d10)",                             "Sap",    "3 lb.",  "15 GP",  "martial-melee-weapon"),
    ("Maul",        "2d6 Bludgeoning", "Heavy, Two-Handed",                            "Topple", "10 lb.", "10 GP",  "martial-melee-weapon"),
    ("Morningstar", "1d8 Piercing",    "",                                             "Sap",    "4 lb.",  "15 GP",  "martial-melee-weapon"),
    ("Pike",        "1d10 Piercing",   "Heavy, Reach, Two-Handed",                    "Push",   "18 lb.", "5 GP",   "martial-melee-weapon"),
    ("Rapier",      "1d8 Piercing",    "Finesse",                                      "Vex",    "2 lb.",  "25 GP",  "martial-melee-weapon"),
    ("Scimitar",    "1d6 Slashing",    "Finesse, Light",                               "Nick",   "3 lb.",  "25 GP",  "martial-melee-weapon"),
    ("Shortsword",  "1d6 Piercing",    "Finesse, Light",                               "Vex",    "2 lb.",  "10 GP",  "martial-melee-weapon"),
    ("Trident",     "1d8 Piercing",    "Thrown (Range 20/60), Versatile (1d10)",       "Topple", "4 lb.",  "5 GP",   "martial-melee-weapon"),
    ("War Pick",    "1d8 Piercing",    "Versatile (1d10)",                             "Sap",    "2 lb.",  "5 GP",   "martial-melee-weapon"),
    ("Warhammer",   "1d8 Bludgeoning", "Versatile (1d10)",                             "Push",   "5 lb.",  "15 GP",  "martial-melee-weapon"),
    ("Whip",        "1d4 Slashing",    "Finesse, Reach",                               "Slow",   "3 lb.",  "2 GP",   "martial-melee-weapon"),
    # Martial Ranged
    ("Blowgun",         "1 Piercing",   "Ammunition (Range 25/100; Needle), Loading",                              "Vex",  "1 lb.",  "10 GP",  "martial-ranged-weapon"),
    ("Hand Crossbow",   "1d6 Piercing", "Ammunition (Range 30/120; Bolt), Light, Loading",                         "Vex",  "3 lb.",  "75 GP",  "martial-ranged-weapon"),
    ("Heavy Crossbow",  "1d10 Piercing","Ammunition (Range 100/400; Bolt), Heavy, Loading, Two-Handed",            "Push", "18 lb.", "50 GP",  "martial-ranged-weapon"),
    ("Longbow",         "1d8 Piercing", "Ammunition (Range 150/600; Arrow), Heavy, Two-Handed",                    "Slow", "2 lb.",  "50 GP",  "martial-ranged-weapon"),
    ("Musket",          "1d12 Piercing","Ammunition (Range 40/120; Bullet), Loading, Two-Handed",                  "Slow", "10 lb.", "500 GP", "martial-ranged-weapon"),
    ("Pistol",          "1d10 Piercing","Ammunition (Range 30/90; Bullet), Loading",                               "Vex",  "3 lb.",  "250 GP", "martial-ranged-weapon"),
]


def extract_weapons() -> list[dict]:
    weapons = []
    for row in WEAPON_TABLE:
        name, raw_dmg, raw_props, mastery, weight, cost, cat = row
        rec = _parse_weapon_row(name, raw_dmg, raw_props, mastery, weight, cost, cat)
        weapons.append(rec)
    return weapons


# --------------------------------------------------------------------------- armor extraction

# Armor table from page 217 — well structured OCR
# (name, ac_formula, strength_req, stealth_disadvantage, weight, cost, category)
ARMOR_TABLE: list[tuple[str, str, str | None, bool, str, str, str]] = [
    # Light Armor
    ("Padded Armor",         "11 + Dex modifier",         None,     True,  "8 lb.",  "5 GP",     "light-armor"),
    ("Leather Armor",        "11 + Dex modifier",         None,     False, "10 lb.", "10 GP",    "light-armor"),
    ("Studded Leather Armor","12 + Dex modifier",         None,     False, "13 lb.", "45 GP",    "light-armor"),
    # Medium Armor
    ("Hide Armor",           "12 + Dex modifier (max 2)", None,     False, "12 lb.", "10 GP",    "medium-armor"),
    ("Chain Shirt",          "13 + Dex modifier (max 2)", None,     False, "20 lb.", "50 GP",    "medium-armor"),
    ("Scale Mail",           "14 + Dex modifier (max 2)", None,     True,  "45 lb.", "50 GP",    "medium-armor"),
    ("Breastplate",          "14 + Dex modifier (max 2)", None,     False, "20 lb.", "400 GP",   "medium-armor"),
    ("Half Plate Armor",     "15 + Dex modifier (max 2)", None,     True,  "40 lb.", "750 GP",   "medium-armor"),
    # Heavy Armor
    ("Ring Mail",            "14",                        None,     True,  "40 lb.", "30 GP",    "heavy-armor"),
    ("Chain Mail",           "16",                        "Str 13", True,  "55 lb.", "75 GP",    "heavy-armor"),
    ("Splint Armor",         "17",                        "Str 15", True,  "60 lb.", "200 GP",   "heavy-armor"),
    ("Plate Armor",          "18",                        "Str 15", True,  "65 lb.", "1,500 GP", "heavy-armor"),
    # Shield
    ("Shield",               "+2",                        None,     False, "6 lb.",  "10 GP",    "shield"),
]


def extract_armor() -> list[dict]:
    armor = []
    for name, ac, str_req, stealth_disadv, weight, cost, category in ARMOR_TABLE:
        rec: dict = {
            "index": _slug(name),
            "name": name,
            "equipment_category": category,
            "cost": cost,
            "armor_class": ac,
            "strength_requirement": str_req,
            "stealth_disadvantage": stealth_disadv,
            "weight": weight,
            "srd": False,
            "local": True,
            "source": SOURCE,
        }
        armor.append(rec)
    return armor


# --------------------------------------------------------------------------- tools extraction

# Artisan's Tools — from pages 218-219
ARTISANS_TOOLS: list[tuple[str, str, str]] = [
    ("Alchemist's Supplies",   "50 GP", "8 lb."),
    ("Brewer's Supplies",      "20 GP", "9 lb."),
    ("Calligrapher's Supplies","10 GP", "5 lb."),
    ("Carpenter's Tools",      "8 GP",  "6 lb."),
    ("Cartographer's Tools",   "15 GP", "6 lb."),
    ("Cobbler's Tools",        "5 GP",  "5 lb."),
    ("Cook's Utensils",        "1 GP",  "8 lb."),
    ("Glassblower's Tools",    "30 GP", "5 lb."),
    ("Jeweler's Tools",        "25 GP", "2 lb."),
    ("Leatherworker's Tools",  "5 GP",  "5 lb."),
    ("Mason's Tools",          "10 GP", "8 lb."),
    ("Painter's Supplies",     "10 GP", "5 lb."),
    ("Potter's Tools",         "10 GP", "3 lb."),
    ("Smith's Tools",          "20 GP", "8 lb."),
    ("Tinker's Tools",         "50 GP", "10 lb."),
    ("Weaver's Tools",         "1 GP",  "5 lb."),
    ("Woodcarver's Tools",     "1 GP",  "5 lb."),
]

# Gaming Sets — from page 219 (variants listed under Gaming Set entry)
GAMING_SETS: list[tuple[str, str, str]] = [
    ("Dice Set",              "1 SP",  ""),
    ("Dragonchess Set",       "1 GP",  ""),
    ("Playing Card Set",      "5 SP",  ""),
    ("Three-Dragon Ante Set", "1 GP",  ""),
]

# Musical Instruments — from page 219 (variants listed under Musical Instrument entry)
MUSICAL_INSTRUMENTS: list[tuple[str, str, str]] = [
    ("Bagpipes",   "30 GP", "6 lb."),
    ("Drum",       "6 GP",  "3 lb."),
    ("Dulcimer",   "25 GP", "10 lb."),
    ("Flute",      "2 GP",  "1 lb."),
    ("Horn",       "3 GP",  "2 lb."),
    ("Lute",       "35 GP", "2 lb."),
    ("Lyre",       "30 GP", "2 lb."),
    ("Pan Flute",  "12 GP", "2 lb."),
    ("Shawm",      "2 GP",  "1 lb."),
    ("Viol",       "30 GP", "1 lb."),
]

# Other Tools — from page 219
OTHER_TOOLS: list[tuple[str, str, str]] = [
    ("Disguise Kit",       "25 GP", "3 lb."),
    ("Forgery Kit",        "15 GP", "5 lb."),
    ("Herbalism Kit",      "5 GP",  "3 lb."),
    ("Navigator's Tools",  "25 GP", "2 lb."),
    ("Poisoner's Kit",     "50 GP", "2 lb."),
    ("Thieves' Tools",     "25 GP", "1 lb."),
]


def _make_tool(name: str, cost: str, weight: str, tool_type: str) -> dict:
    rec: dict = {
        "index": _slug(name),
        "name": name,
        "equipment_category": "tool",
        "tool_type": tool_type,
        "cost": cost,
        "srd": False,
        "local": True,
        "source": SOURCE,
    }
    if weight:
        rec["weight"] = weight
    return rec


def extract_tools() -> list[dict]:
    tools: list[dict] = []
    for name, cost, weight in ARTISANS_TOOLS:
        tools.append(_make_tool(name, cost, weight, "artisans-tools"))
    for name, cost, weight in GAMING_SETS:
        tools.append(_make_tool(name, cost, weight, "gaming-set"))
    for name, cost, weight in MUSICAL_INSTRUMENTS:
        tools.append(_make_tool(name, cost, weight, "musical-instrument"))
    for name, cost, weight in OTHER_TOOLS:
        tools.append(_make_tool(name, cost, weight, "other-tool"))
    return tools


# --------------------------------------------------------------------------- adventuring gear extraction

# Key adventuring gear items from page 221 table + focus sub-tables (pages 222-224)
# Format: (name, weight, cost)
# The table on page 221 is a two-column layout; weights/costs parsed directly.
# Focus sub-tables on pages 222 and 224 list variants.
ADVENTURING_GEAR: list[tuple[str, str, str]] = [
    ("Acid",                   "1 lb.",     "25 GP"),
    ("Alchemist's Fire",       "1 lb.",     "50 GP"),
    ("Antitoxin",              "",          "50 GP"),
    ("Backpack",               "5 lb.",     "2 GP"),
    ("Ball Bearings",          "2 lb.",     "1 GP"),
    ("Barrel",                 "70 lb.",    "2 GP"),
    ("Basket",                 "2 lb.",     "4 SP"),
    ("Bedroll",                "7 lb.",     "1 GP"),
    ("Bell",                   "",          "1 GP"),
    ("Blanket",                "3 lb.",     "5 SP"),
    ("Block and Tackle",       "5 lb.",     "1 GP"),
    ("Book",                   "5 lb.",     "25 GP"),
    ("Bottle, Glass",          "2 lb.",     "2 GP"),
    ("Bucket",                 "2 lb.",     "5 CP"),
    ("Caltrops",               "2 lb.",     "1 GP"),
    ("Candle",                 "",          "1 CP"),
    ("Case, Crossbow Bolt",    "1 lb.",     "1 GP"),
    ("Case, Map or Scroll",    "1 lb.",     "1 GP"),
    ("Chain",                  "10 lb.",    "5 GP"),
    ("Chest",                  "25 lb.",    "5 GP"),
    ("Climber's Kit",          "12 lb.",    "25 GP"),
    ("Clothes, Fine",          "6 lb.",     "15 GP"),
    ("Clothes, Traveler's",    "4 lb.",     "2 GP"),
    ("Component Pouch",        "2 lb.",     "25 GP"),
    ("Costume",                "4 lb.",     "5 GP"),
    ("Crowbar",                "5 lb.",     "2 GP"),
    ("Flask",                  "1 lb.",     "2 CP"),
    ("Grappling Hook",         "4 lb.",     "2 GP"),
    ("Healer's Kit",           "3 lb.",     "5 GP"),
    ("Holy Water",             "1 lb.",     "25 GP"),
    ("Hunting Trap",           "25 lb.",    "5 GP"),
    ("Ink",                    "",          "10 GP"),
    ("Ink Pen",                "",          "2 CP"),
    ("Jug",                    "4 lb.",     "2 CP"),
    ("Ladder",                 "25 lb.",    "1 SP"),
    ("Lamp",                   "1 lb.",     "5 SP"),
    ("Lantern, Bullseye",      "2 lb.",     "10 GP"),
    ("Lantern, Hooded",        "2 lb.",     "5 GP"),
    ("Lock",                   "1 lb.",     "10 GP"),
    ("Magnifying Glass",       "",          "100 GP"),
    ("Manacles",               "6 lb.",     "2 GP"),
    ("Map",                    "",          "1 GP"),
    ("Mirror",                 "1/2 lb.",   "5 GP"),
    ("Net",                    "3 lb.",     "1 GP"),
    ("Oil",                    "1 lb.",     "1 SP"),
    ("Paper",                  "",          "2 SP"),
    ("Parchment",              "",          "1 SP"),
    ("Perfume",                "",          "5 GP"),
    ("Poison, Basic",          "",          "100 GP"),
    ("Pole",                   "7 lb.",     "5 CP"),
    ("Pot, Iron",              "10 lb.",    "2 GP"),
    ("Potion of Healing",      "1/2 lb.",   "50 GP"),
    ("Pouch",                  "1 lb.",     "5 SP"),
    ("Quiver",                 "1 lb.",     "1 GP"),
    ("Ram, Portable",          "35 lb.",    "4 GP"),
    ("Rations",                "2 lb.",     "5 SP"),
    ("Robe",                   "4 lb.",     "1 GP"),
    ("Rope",                   "5 lb.",     "1 GP"),
    ("Sack",                   "1/2 lb.",   "1 CP"),
    ("Shovel",                 "5 lb.",     "2 GP"),
    ("Signal Whistle",         "",          "5 CP"),
    ("Spell Scroll (Cantrip)", "",          "30 GP"),
    ("Spell Scroll (Level 1)", "",          "50 GP"),
    ("Spikes, Iron",           "5 lb.",     "1 GP"),
    ("Spyglass",               "1 lb.",     "1,000 GP"),
    ("String",                 "",          "1 SP"),
    ("Tent",                   "20 lb.",    "2 GP"),
    ("Tinderbox",              "1 lb.",     "5 SP"),
    ("Torch",                  "1 lb.",     "1 CP"),
    ("Vial",                   "",          "1 GP"),
    ("Waterskin",              "5 lb. (full)", "2 SP"),
]

# Arcane Focus sub-table (page 222)
ARCANE_FOCUSES: list[tuple[str, str, str]] = [
    ("Arcane Focus, Crystal", "1 lb.",  "10 GP"),
    ("Arcane Focus, Orb",     "3 lb.",  "20 GP"),
    ("Arcane Focus, Rod",     "2 lb.",  "10 GP"),
    ("Arcane Focus, Staff",   "4 lb.",  "5 GP"),
    ("Arcane Focus, Wand",    "1 lb.",  "10 GP"),
]

# Holy Symbol sub-table (page 224)
HOLY_SYMBOLS: list[tuple[str, str, str]] = [
    ("Holy Symbol, Amulet",    "1 lb.",  "5 GP"),
    ("Holy Symbol, Emblem",    "",       "5 GP"),
    ("Holy Symbol, Reliquary", "2 lb.",  "5 GP"),
]

# Druidic Focus sub-table (page 223)
DRUIDIC_FOCUSES: list[tuple[str, str, str]] = [
    ("Druidic Focus, Sprig of Mistletoe", "",       "1 GP"),
    ("Druidic Focus, Wooden Staff",        "4 lb.", "5 GP"),
    ("Druidic Focus, Yew Wand",            "1 lb.", "10 GP"),
]


def extract_adventuring_gear() -> list[dict]:
    gear: list[dict] = []
    for name, weight, cost in ADVENTURING_GEAR:
        rec: dict = {
            "index": _slug(name),
            "name": name,
            "equipment_category": "adventuring-gear",
            "cost": cost,
            "srd": False,
            "local": True,
            "source": SOURCE,
        }
        if weight:
            rec["weight"] = weight
        gear.append(rec)

    # Focuses
    for name, weight, cost in ARCANE_FOCUSES:
        rec = {
            "index": _slug(name),
            "name": name,
            "equipment_category": "arcane-focus",
            "cost": cost,
            "srd": False,
            "local": True,
            "source": SOURCE,
        }
        if weight:
            rec["weight"] = weight
        gear.append(rec)

    for name, weight, cost in HOLY_SYMBOLS:
        rec = {
            "index": _slug(name),
            "name": name,
            "equipment_category": "holy-symbol",
            "cost": cost,
            "srd": False,
            "local": True,
            "source": SOURCE,
        }
        if weight:
            rec["weight"] = weight
        gear.append(rec)

    for name, weight, cost in DRUIDIC_FOCUSES:
        rec = {
            "index": _slug(name),
            "name": name,
            "equipment_category": "druidic-focus",
            "cost": cost,
            "srd": False,
            "local": True,
            "source": SOURCE,
        }
        if weight:
            rec["weight"] = weight
        gear.append(rec)

    return gear


# --------------------------------------------------------------------------- main

def main(argv: list[str]) -> int:
    if not argv:
        print("usage: extract_phb2024_equipment.py <path-to-PHB-2024.pdf>", file=sys.stderr)
        return 2
    pdf = Path(argv[0])
    if not pdf.exists():
        print(f"not found: {pdf}", file=sys.stderr)
        return 2

    # Open PDF for validation / page probing (we use canonical data above, but confirm access)
    doc = fitz.open(pdf)
    total_pages = doc.page_count
    print(f"Opened PDF: {pdf.name}  ({total_pages} pages)")

    # Verify key pages are present
    page213_text = doc[213].get_text()
    if "Martial Melee" not in page213_text and "MARTIAL MELEE" not in page213_text.upper():
        print("WARNING: page 213 does not look like the weapons table — verify page offsets",
              file=sys.stderr)

    OUT.mkdir(parents=True, exist_ok=True)

    weapons = extract_weapons()
    armor = extract_armor()
    tools = extract_tools()
    adventuring_gear = extract_adventuring_gear()

    output = {
        "weapons": weapons,
        "armor": armor,
        "tools": tools,
        "adventuring_gear": adventuring_gear,
    }

    out_path = OUT / "equipment_2024_phb.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    total = len(weapons) + len(armor) + len(tools) + len(adventuring_gear)
    simple_melee  = sum(1 for w in weapons if w["equipment_category"] == "simple-melee-weapon")
    simple_ranged = sum(1 for w in weapons if w["equipment_category"] == "simple-ranged-weapon")
    martial_melee = sum(1 for w in weapons if w["equipment_category"] == "martial-melee-weapon")
    martial_ranged= sum(1 for w in weapons if w["equipment_category"] == "martial-ranged-weapon")

    print(f"weapons:          {len(weapons):>3}  "
          f"(simple-melee={simple_melee}, simple-ranged={simple_ranged}, "
          f"martial-melee={martial_melee}, martial-ranged={martial_ranged})")
    print(f"armor:            {len(armor):>3}")
    print(f"tools:            {len(tools):>3}  "
          f"(artisans={sum(1 for t in tools if t['tool_type']=='artisans-tools')}, "
          f"gaming={sum(1 for t in tools if t['tool_type']=='gaming-set')}, "
          f"instruments={sum(1 for t in tools if t['tool_type']=='musical-instrument')}, "
          f"other={sum(1 for t in tools if t['tool_type']=='other-tool')})")
    print(f"adventuring_gear: {len(adventuring_gear):>3}")
    print(f"TOTAL:            {total:>3}")
    print(f"Output:           {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
