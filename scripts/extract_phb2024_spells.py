#!/usr/bin/env python
"""LOCAL-ONLY extractor: 2024 PHB spell descriptions -> data/local/spells_2024_phb.json

Reads a copyrighted rulebook PDF the user supplies locally and writes ONLY to data/local/
(gitignored). For personal prototyping only -- NEVER commit or ship it.

Strategy:
  PASS 1 -- concatenate all spell-chapter pages (237-341) into a line list.
  PASS 2 -- locate spell-name candidates: ALL-CAPS lines followed within 4 lines by a
            "Level N <school>" or "<school> Cantrip" line.
  PASS 3 -- filter out OCR garbage (chapter headers, image captions, stat-block lines).
  PASS 4 -- for each real candidate, parse structured header fields then collect body text
            until the next candidate.

Usage: python scripts/extract_phb2024_spells.py "PDFs/D&D 5E [2024] PHB.pdf"
"""
from __future__ import annotations

import json
import re
import sys
from difflib import get_close_matches
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "local"
SOURCE = {
    "name": "Player's Handbook (2024)",
    "publisher": "Wizards of the Coast",
    "license": "All rights reserved (local prototyping only)",
}

# ── helpers ──────────────────────────────────────────────────────────────────

OCR_JUNK = re.compile(
    r"[⊠�]|[:;]{2,}|[a-z][:;~^|][a-z]|\s[:;~^|]\s|[~^|]{1,}|\(cid:"
)
OCR_DICE = re.compile(r"\bl(d(?:4|6|8|10|12|20|100))\b")
OCR_ORD = re.compile(r"\bl(st|nd|rd|th)\b")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def _clean(text: str) -> str:
    text = re.sub(r"-\s*\n\s*", "", text)
    text = text.replace("\n", " ")
    text = re.sub(r"([a-z])-\s+([a-z])", r"\1\2", text)
    # strip page furniture
    text = re.sub(
        r"\bCH\s*\\?\s*[APT]{1,2}TE?\s*R\b.{0,4}\d.{0,60}?(?:SPELLS?|MAGIC)\b\s*\S*",
        " ",
        text,
        flags=re.I,
    )
    text = re.sub(r"\s+", " ", text)
    text = OCR_DICE.sub(r"1\1", text)
    text = OCR_ORD.sub(r"1\1", text)
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")  # ligatures
    text = re.sub(r"[\s~^|;:=_•\-]{2,}$", "", text)
    return text.strip()


def _despace(s: str) -> str:
    """Collapse OCR letter-spacing: 'K E E N' -> 'KEEN'."""
    prev = None
    while s != prev:
        prev = s
        s = re.sub(r"\b([A-Z]) (?=[A-Z])", r"\1", s)
        s = re.sub(r"(?<=[A-Z]) ([A-Z])\b", r"\1", s)
    return s


def _key(s: str) -> str:
    """Fold OCR digit-for-letter swaps and strip non-alpha for fuzzy matching."""
    s = s.lower().replace("0", "o").replace("1", "l")
    return re.sub(r"[^a-z]", "", s)


# ── canonical spell name list ─────────────────────────────────────────────────

CANON_SPELLS = [
    # Cantrips
    "Acid Splash", "Blade Ward", "Chill Touch", "Dancing Lights", "Druidcraft",
    "Eldritch Blast", "Fire Bolt", "Friends", "Guidance", "Light", "Mage Hand",
    "Mending", "Message", "Minor Illusion", "Poison Spray", "Prestidigitation",
    "Produce Flame", "Ray of Frost", "Resistance", "Sacred Flame", "Shillelagh",
    "Shocking Grasp", "Spare the Dying", "Thaumaturgy", "Thorn Whip", "Thunderclap",
    "True Strike", "Vicious Mockery", "Word of Radiance",
    # Cantrips new in 2024
    "Elementalism", "Sorcerous Burst", "Starry Wisp", "Toll the Dead",
    # Level 1
    "Alarm", "Animal Friendship", "Armor of Agathys", "Arms of Hadar", "Bane",
    "Bless", "Burning Hands", "Charm Person", "Chromatic Orb", "Color Spray",
    "Command", "Compelled Duel", "Comprehend Languages", "Create or Destroy Water",
    "Cure Wounds", "Detect Evil and Good", "Detect Magic", "Detect Poison and Disease",
    "Disguise Self", "Dissonant Whispers", "Divine Favor", "Earth Tremor",
    "Ensnaring Strike", "Entangle", "Expeditious Retreat", "Faerie Fire",
    "False Life", "Feather Fall", "Find Familiar", "Fog Cloud", "Goodberry",
    "Grease", "Guiding Bolt", "Healing Word", "Hellish Rebuke", "Heroism",
    "Hex", "Hunter's Mark", "Ice Knife", "Identify", "Illusory Script",
    "Inflict Wounds", "Jump", "Longstrider", "Mage Armor", "Magic Missile",
    "Protection from Evil and Good", "Purify Food and Drink", "Ray of Sickness",
    "Sanctuary", "Searing Smite", "Shield", "Shield of Faith", "Silent Image",
    "Sleep", "Snare", "Speak with Animals", "Tasha's Hideous Laughter",
    "Tenser's Floating Disk", "Thunderwave", "Unseen Servant",
    "Witch Bolt", "Wrathful Smite",
    # Level 2
    "Aid", "Alter Self", "Animal Messenger", "Arcane Lock", "Arcane Vigor",
    "Augury", "Barkskin", "Beast Sense", "Blindness/Deafness", "Blur",
    "Calm Emotions", "Cloud of Daggers", "Continual Flame", "Cordon of Arrows",
    "Crown of Madness", "Darkness", "Darkvision", "Detect Thoughts",
    "Dragon's Breath", "Dust Devil", "Earthbind", "Enhance Ability",
    "Enlarge/Reduce", "Enthrall", "Find Steed", "Find Traps", "Flame Blade",
    "Flaming Sphere", "Gentle Repose", "Gust of Wind", "Heat Metal",
    "Hold Person", "Invisibility", "Knock", "Lesser Restoration", "Levitate",
    "Locate Animals or Plants", "Locate Object", "Magic Mouth", "Magic Weapon",
    "Maximilian's Earthen Grasp", "Melf's Acid Arrow", "Mind Spike",
    "Mirror Image", "Misty Step", "Moonbeam", "Nystul's Magic Aura",
    "Pass without Trace", "Phantasmal Force", "Prayer of Healing",
    "Protection from Poison", "Pyrotechnics", "Ray of Enfeeblement",
    "Rope Trick", "Scorching Ray", "See Invisibility", "Shadow Blade",
    "Shatter", "Silence", "Skywrite", "Snilloc's Snowball Swarm",
    "Spider Climb", "Spike Growth", "Spiritual Weapon", "Suggestion",
    "Warding Bond", "Web", "Zone of Truth",
    # Level 3
    "Animate Dead", "Aura of Vitality", "Beacon of Hope", "Bestow Curse",
    "Blink", "Call Lightning", "Clairvoyance", "Conjure Animals",
    "Conjure Barrage", "Counterspell", "Create Food and Water", "Crusader's Mantle",
    "Daylight", "Dispel Magic", "Elemental Weapon", "Enemies Abound",
    "Erupting Earth", "Fear", "Feign Death", "Fireball", "Fly", "Gaseous Form",
    "Glyph of Warding", "Haste", "Hunger of Hadar", "Hypnotic Pattern",
    "Leomund's Tiny Hut", "Life Transference", "Lightning Bolt",
    "Magic Circle", "Major Image", "Mass Healing Word", "Meld into Stone",
    "Melf's Minute Meteors", "Nondetection", "Phantom Steed", "Plant Growth",
    "Protection from Energy", "Remove Curse", "Revivify", "Sending",
    "Sleet Storm", "Slow", "Speak with Dead", "Speak with Plants",
    "Spirit Guardians", "Stinking Cloud", "Summon Fey", "Summon Lesser Demons",
    "Summon Shadowspawn", "Summon Undead", "Thunder Step", "Tidal Wave",
    "Tiny Servant", "Tongues", "Vampiric Touch", "Wall of Sand", "Wall of Water",
    "Water Breathing", "Water Walk", "Wind Wall",
    # Level 4
    "Arcane Eye", "Aura of Life", "Aura of Purity", "Banishment",
    "Blight", "Charm Monster", "Compulsion", "Confusion",
    "Conjure Minor Elementals", "Conjure Woodland Beings", "Control Water",
    "Death Ward", "Dimension Door", "Divination", "Dominate Beast",
    "Elemental Bane", "Evard's Black Tentacles", "Fabricate", "Fire Shield",
    "Fount of Moonlight", "Freedom of Movement", "Giant Insect",
    "Grasping Vine", "Greater Invisibility", "Guardian of Faith",
    "Hallucinatory Terrain", "Ice Storm", "Leomund's Secret Chest",
    "Locate Creature", "Mordenkainen's Faithful Hound",
    "Mordenkainen's Private Sanctum", "Otiluke's Resilient Sphere",
    "Phantasmal Killer", "Polymorph", "Raulothim's Psychic Lance",
    "Shadow of Moil", "Sickening Radiance", "Spirit of Death", "Staggering Smite",
    "Stone Shape", "Stoneskin", "Storm Sphere", "Summon Aberration",
    "Summon Construct", "Summon Elemental", "Vitriolic Sphere",
    "Wall of Fire", "Watery Sphere",
    # Level 5
    "Animate Objects", "Antilife Shell", "Arcane Hand",
    "Banishing Smite", "Bigby's Hand", "Circle of Power", "Cloudkill",
    "Commune", "Commune with Nature", "Cone of Cold", "Conjure Elemental",
    "Conjure Volley", "Contact Other Plane", "Contagion",
    "Control Winds", "Creation", "Danse Macabre", "Dawn",
    "Destructive Wave", "Dispel Evil and Good", "Dominate Person",
    "Dream", "Enervation", "Far Step", "Flame Strike",
    "Geas", "Greater Restoration", "Hallow", "Hold Monster", "Holy Weapon",
    "Infernal Calling", "Insect Plague", "Jallarzi's Storm of Radiance",
    "Legend Lore", "Maelstrom", "Mass Cure Wounds", "Mislead",
    "Modify Memory", "Negative Energy Flood", "Passwall", "Planar Binding",
    "Raise Dead", "Rary's Telepathic Bond", "Reincarnate", "Scrying",
    "Seeming", "Skill Empowerment", "Steel Wind Strike", "Summon Celestial",
    "Summon Dragon", "Swift Quiver", "Synaptic Static", "Telekinesis",
    "Telepathic Bond", "Teleportation Circle", "Transmute Rock", "Tree Stride",
    "Wall of Force", "Wall of Light", "Wall of Stone", "Wrath of Nature",
    "Yolande's Regal Presence",
    # Level 6
    "Arcane Gate", "Blade Barrier", "Bones of the Earth",
    "Chain Lightning", "Circle of Death", "Contingency",
    "Create Undead", "Disintegrate", "Drawmij's Instant Summons",
    "Druid Grove", "Eyebite", "Find the Path", "Flesh to Stone",
    "Forbiddance", "Globe of Invulnerability", "Guards and Wards",
    "Harm", "Heal", "Heroes' Feast", "Investiture of Flame",
    "Investiture of Ice", "Investiture of Stone", "Investiture of Wind",
    "Magic Jar", "Mass Suggestion", "Mental Prison", "Move Earth",
    "Otiluke's Freezing Sphere", "Otto's Irresistible Dance",
    "Planar Ally", "Programmed Illusion", "Scatter", "Soul Cage",
    "Summon Fiend", "Sunbeam", "Tasha's Bubbling Cauldron",
    "Tenser's Transformation", "Transport via Plants",
    "True Seeing", "Wall of Ice", "Wall of Thorns", "Wind Walk", "Word of Recall",
    # Level 7
    "Conjure Celestial", "Crown of Stars", "Delayed Blast Fireball",
    "Divine Word", "Etherealness", "Finger of Death", "Fire Storm",
    "Forcecage", "Mirage Arcane", "Mordenkainen's Magnificent Mansion",
    "Mordenkainen's Sword", "Plane Shift", "Power Word Fortify",
    "Power Word Pain", "Prismatic Spray", "Project Image",
    "Regenerate", "Resurrection", "Reverse Gravity", "Sequester",
    "Simulacrum", "Symbol", "Teleport", "Temple of the Gods",
    "Tether Essence", "Whirlwind",
    # Level 8
    "Abi-Dalzim's Horrid Wilting", "Animal Shapes", "Antimagic Field",
    "Antipathy/Sympathy", "Befuddlement", "Clone", "Control Weather",
    "Dark Star", "Demiplane", "Dominate Monster", "Earthquake",
    "Feeblemind", "Glibness", "Holy Aura", "Illusory Dragon",
    "Incendiary Cloud", "Maddening Darkness", "Maze", "Mind Blank",
    "Power Word Stun", "Reality Break", "Sunburst", "Telepathy",
    "Tsunami",
    # Level 9
    "Astral Projection", "Blade of Disaster", "Foresight",
    "Gate", "Imprisonment", "Invulnerability", "Mass Heal",
    "Mass Polymorph", "Meteor Swarm", "Power Word Heal",
    "Power Word Kill", "Prismatic Wall", "Psychic Scream",
    "Ravenous Void", "Shapechange", "Storm of Vengeance",
    "Time Ravage", "Time Stop", "True Polymorph", "True Resurrection",
    "Weird", "Wish",
    # Extra spells added in 2024 that may not be in original list
    "Awaken", "Lightning Arrow", "Summon Beast",
]

CANON_BY_KEY = {_key(n): n for n in CANON_SPELLS}
CANON_KEY_LIST = list(CANON_BY_KEY.keys())


def _repair_spell_name(raw: str) -> tuple[str, str]:
    """Return (best-effort name, status) where status in {'exact', 'fuzzy', 'suspect'}."""
    despc = _despace(raw.strip())
    dk = _key(despc)
    if dk in CANON_BY_KEY:
        return CANON_BY_KEY[dk], "exact"
    close = get_close_matches(dk, CANON_KEY_LIST, n=1, cutoff=0.72)
    if close:
        return CANON_BY_KEY[close[0]], "fuzzy"
    return despc.title(), "suspect"


# ── school detection ──────────────────────────────────────────────────────────

SCHOOL_RE = re.compile(
    r"\b(Abjuration|Conjuration|Divination|Enchantment|Evocation|Illusion|Necromancy|Transmutation)\b",
    re.I,
)


def _parse_level_school(line: str) -> tuple[int | None, str | None, bool]:
    """Return (level, school, is_cantrip). level=0 for cantrips. None if no match."""
    line = line.strip()
    if re.search(r"\bCantrip\b", line, re.I):
        sm = SCHOOL_RE.search(line)
        return 0, (sm.group(1).lower() if sm else None), True
    lm = re.match(r"(?i)^Level\s+([0-9IlOJ]{1,2})\s+(\w+)", line)
    if lm:
        lvl_raw = lm.group(1).upper().replace("I", "1").replace("L", "1").replace("O", "0").replace("J", "1")
        try:
            lvl = int(lvl_raw)
        except ValueError:
            lvl = 1
        sm = SCHOOL_RE.search(line)
        school = sm.group(1).lower() if sm else lm.group(2).lower()
        return lvl, school, False
    return None, None, False


# ── component parsing ─────────────────────────────────────────────────────────

def _parse_components(comp_line: str) -> tuple[list[str], str]:
    """Return (component_list, material_text)."""
    comp_line = re.sub(r"(?i)^Components?:\s*", "", comp_line).strip()
    material = ""
    mat_m = re.search(r"\((.+)\)\s*$", comp_line, re.S)
    if mat_m:
        material = _clean(mat_m.group(1))
        comp_line = comp_line[: mat_m.start()].strip()
    comps = re.findall(r"\b[VSM]\b", comp_line)
    comps = sorted(set(comps), key=lambda c: ["V", "S", "M"].index(c) if c in "VSM" else 99)
    return comps, material


# ── junk / false-positive detection ──────────────────────────────────────────

# Patterns that identify OCR garbage: chapter headers, image captions, stat-block markers.
# Tested against the raw (pre-despace) ALL-CAPS line.
def _dejunk_key(s: str) -> str:
    """Collapse whitespace and lowercase for junk-pattern matching."""
    return re.sub(r"\s+", "", s).lower()


def _is_chapter_header(s: str) -> bool:
    """Detect OCR'd 'CHAPTER 7 | SPELLS' page footer in its many garbled forms."""
    # Remove internal whitespace for matching, then look for chapter+digit+spells pattern
    compressed = _dejunk_key(s)
    # matches: chapter7ispells, chapt7ispells, chaptbr7ispells, c:hapter7, etc.
    return bool(re.search(r"(?i)(c\s*[h:]\s*a\s*p\s*t?\s*[e3]\s*r?\s*\d|\bchap\b)", compressed)
                and re.search(r"(?i)(spell|ells|ell)", compressed))


JUNK_PATTERNS = [
    # Chapter header / page footer in many OCR-garbled variants
    # Handled by _is_chapter_header() above, but keep a few explicit patterns as backup
    re.compile(r"(?i)CHAPTER\s*\d"),            # CHAPTER 7 ISPELLS ...
    re.compile(r"(?i)C\s*H\s*A\s*P\s*T?\s*E?\s*R\s*\d"),   # C H APT ER 7 ...
    re.compile(r"(?i)C\s*:\s*H\s*A\s*P"),       # C:HAPTER ...
    re.compile(r"(?i)I\s*SP\s*\.?\s*ELLS?\b"),  # ISP.ELLS / I SP ELLS (spaced out)
    re.compile(r"(?i)\bI\s*SPELLS?\b"),          # I SPELLS (spaced "I SPELLS" = pipe + SPELLS)
    re.compile(r"(?i)\bSPELL\s*0?\s*[A-Z\s]{0,4}PTIONS"),  # SPELL DESCRIPTIONS garbled
    re.compile(r"(?i)^SPELL\s+\d"),              # SPELL 0 ES CRI PTIONS etc.
    re.compile(r"(?i)^S\s*P\s*I\s*R\s*IT"),     # SPIRITS SUMMONED BY FIND FAMILIAR (caption)
    re.compile(r"(?i)^ABERRANT\s+SPIRIT"),       # stat block header caption
    re.compile(r"(?i)^A\s*HUM"),                 # A HUMAN DRUID USES SPEAK WITH ANIMALS
    re.compile(r"(?i)^O\s*F\s*THE\s+M"),         # OF THE MUNDANE AND THE WHIMSICAL (caption)
    re.compile(r"(?i)^O\s*F\s*T\s*H\s*E\s*M"),  # OF THE MUNDANE... spaced
    re.compile(r"(?i)^A\s*SPELL\s*C"),           # A SPELL CASTER COULD USE ... (caption)
    re.compile(r"(?i)^w\s*/\\\\?\s*T\s*C"),      # w/\TC.H 0O GTOAPPE/\R ... (caption)
    re.compile(r"/\\"),                          # /\ OCR artifact
    re.compile(r"[/\\]{2}"),                     # \\ backslash noise
    re.compile(r"\(cid:"),                       # PDF char id garbage
    re.compile(r"[⊠�]"),                    # replacement chars
    re.compile(r"(?i)^7\s*[-\s]*I\s*S"),         # "7- IS��LLS" (page num leak)
    re.compile(r"(?i)^OHA\s*PT"),                # "OHAPTBll 7 ISPELLS..." garbled CHAPTER
    re.compile(r"(?i)HAI\s*L\s*O\s*F\s*L?\s*'?H"),  # HAI LOF l'HORNS caption
    re.compile(r"(?i)^II\s*'?\s*$"),             # "II'" (too short, spurious)
    re.compile(r"(?i)^\d+-?\s*I"),               # starts with digit + I (page num)
    re.compile(r"(?i)^DIVINE\s+SMITE\b"),        # Paladin class feature, not a spell
    re.compile(r"[!]{2,}|[;]{2,}|[{]"),         # !! or ;; or { = OCR garbage noise
    re.compile(r"[^\x00-\x7F]"),                 # any non-ASCII = definitely garble in a name line
]

# Known raw OCR names that are real spells but OCR is too garbled to match canonically.
# Map raw_key -> canonical name.
RAW_KEY_OVERRIDES: dict[str, str] = {
    # B rGBY's HAND -> Bigby's Hand
    _key("B rGBY's HAND"): "Bigby's Hand",
    _key("B RGBY'S HAND"): "Bigby's Hand",
    _key("BRGBYS HAND"): "Bigby's Hand",
    # CRUSADER'SMANTLE -> Crusader's Mantle
    _key("CRUSADER'SMANTLE"): "Crusader's Mantle",
    _key("CRUSADERS MANTLE"): "Crusader's Mantle",
    # TENSER 1S FLOATING DISK -> Tenser's Floating Disk
    _key("TENSER 1S FLOATING DISK"): "Tenser's Floating Disk",
    # YOLANDE'SREGAL PRESENCE -> Yolande's Regal Presence
    _key("YOLANDE'SREGAL PRESENCE"): "Yolande's Regal Presence",
    _key("YOLANDESREGAL PRESENCE"): "Yolande's Regal Presence",
    # JALLARZI's STORM OF RADIANCE -> Jallarzi's Storm of Radiance
    _key("JALLARZI'S STORM OF RADIANCE"): "Jallarzi's Storm of Radiance",
    # foUNT OF MOONLIGHT -> Fount of Moonlight
    _key("fOUNT OF MOONLIGHT"): "Fount of Moonlight",
    _key("FOUNT OF MOONLIGHT"): "Fount of Moonlight",
    # MELF 1S ACID ARROW -> Melf's Acid Arrow
    _key("MELF 1S ACID ARROW"): "Melf's Acid Arrow",
    # OTILUKE 1S FREEZING SPH ERE -> Otiluke's Freezing Sphere
    _key("OTILUKE 1S FREEZING SPHERE"): "Otiluke's Freezing Sphere",
    _key("OTILUKE 1S FREEZING SPH ERE"): "Otiluke's Freezing Sphere",
    # RARY'ST l:: LEPATH ICB?ND -> Rary's Telepathic Bond
    _key("RARYST LEPATH ICB ND"): "Rary's Telepathic Bond",
    # STAGGERING SM ITE -> Staggering Smite
    _key("STAGGERING SM ITE"): "Staggering Smite",
    # SUMMON BEAST (OCR matches Summon Aberration wrongly)
    _key("SUMMON BEAST"): "Summon Beast",
    # DIVINE FA"OR (with OCR noise chars) -> Divine Favor
    "divinefaor": "Divine Favor",
    "divinefor": "Divine Favor",
    # CONJURE 1:^EY is actually Conjure Fey (Level 6) -- but in PHB 2024 it's "Conjure Fey" not in SRD
    # The OCR reads 'CONJURE 1:^EY' -- check: the text says "Level 6 Conjuration (Druid)" = Conjure Fey
    _key("CONJURE 1 EY"): "Conjure Fey",
    _key("CONJURE 1:EY"): "Conjure Fey",
    # LIGHTNING ARROW (PHB 2024 keeps this name, not Lightning Bolt which is separate)
    # The OCR shows 'LIGHTNING ARROW' already - it IS a separate spell from Lightning Bolt
    _key("LIGHTNING ARROW"): "Lightning Arrow",
    # ELEMENTALISM cantrip
    _key("ELEMENTALISM"): "Elementalism",
    # THUNDEROUS SMITE (a different spell from Thunder Step - OCR matched Thunder Step to this)
    _key("THUNDEROUS SMITE"): "Thunderous Smite",
}

# Add Thunderous Smite and Conjure Fey and Lightning Arrow to canonical if not present
_EXTRA = ["Conjure Fey", "Lightning Arrow", "Thunderous Smite"]
for _n in _EXTRA:
    if _key(_n) not in CANON_BY_KEY:
        CANON_BY_KEY[_key(_n)] = _n
        CANON_KEY_LIST.append(_key(_n))


def _is_junk(raw_name: str, check_overrides: bool = True) -> bool:
    """Return True if the raw ALL-CAPS name is page furniture or an image caption.

    If check_overrides=True, a name present in RAW_KEY_OVERRIDES is never considered junk
    (it's a real spell with garbled name that we know how to fix).
    """
    if check_overrides:
        rk = _key(raw_name)
        if rk in RAW_KEY_OVERRIDES:
            return False  # known real spell with garbled name
    if _is_chapter_header(raw_name):
        return True
    for pat in JUNK_PATTERNS:
        if pat.search(raw_name):
            return True
    return False


# ── main extraction ───────────────────────────────────────────────────────────

SPELL_START_PAGE = 237
SPELL_END_PAGE = 341   # inclusive


def _is_spell_name_candidate(line: str) -> bool:
    """True if the line could be a spell name header (mostly uppercase, right length)."""
    s = line.strip()
    if not s or len(s) > 65:
        return False
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 2:
        return False
    upper_ratio = sum(c.isupper() for c in letters) / len(letters)
    if upper_ratio < 0.70:
        return False
    # exclude lines that obviously start with field labels or numbers
    skip = [
        r"^(Casting Time|Range|Components?|Duration|CHAPTER|APPENDIX|LEVEL\s+\d|CANTRIP UPGRADE)",
        r"^(USING A HIGHER|ACTIONS?|MOD|SAVE|STR|DEX|CON|INT|WIS|CHA)\b",
        r"^(AC|HP|CR|XP|PB|TRAITS?|IMMUNITIES?|SKILLS?|SENSES?|LANGUAGES?|SPEED|INITIATIVE|RESISTANCES)\b",
        r"^\d+\s+[A-Z]",   # page number at start
    ]
    for pat in skip:
        if re.match(pat, s, re.I):
            return False
    # real spell names: no period anywhere (image captions end with "FRIEND." or have "FRIEND. SPEAK")
    if "." in s and not re.match(r"(?i)^(Abi-Dalzim|Blindness|Enlarge)", s):
        # The only '.' in real spell names is in "Abi-Dalzim's" (not a period) or abbreviations
        # Actually spell names don't end with '.' or have '.' in the middle
        # Exception: "Tasha's" apostrophe is not a period; check for literal period
        if re.search(r"\.", s):
            return False
    # too many words (> 6) is almost always a caption or body text
    if len(s.split()) > 6:
        return False
    # contains obviously non-spell characters (OCR artifacts specific to captions/glyphs)
    if re.search(r"[/\\|{}<>@#%^~`]", s):
        return False
    # contains non-ASCII non-letter characters that appear only in OCR garble
    # (checkmarks, box chars, curly quotes embedded in ALL-CAPS lines, etc.)
    non_ascii_letters = [c for c in s if ord(c) > 127 and not c.isalpha()]
    if non_ascii_letters:
        return False
    return True


def extract_spells(doc) -> list[dict]:
    # Gather all lines from the spells chapter
    all_lines: list[str] = []
    for p in range(SPELL_START_PAGE, SPELL_END_PAGE + 1):
        all_lines.extend(doc[p].get_text().splitlines())

    def _is_garbled_name_before_level(line: str) -> bool:
        """True if line is clearly a garbled spell name (non-ASCII chars, but not pure body text).
        These lines have OCR-mangled spell names like 'DIVINE FA"✓OR'."""
        s = line.strip()
        if not s or len(s) > 65:
            return False
        letters = [c for c in s if c.isalpha()]
        if len(letters) < 2:
            return False
        upper_ratio = sum(c.isupper() for c in letters) / len(letters)
        if upper_ratio < 0.60:
            return False
        # Must have some non-ASCII chars (that's why it failed the normal check)
        non_ascii_non_letter = [c for c in s if ord(c) > 127 and not c.isalpha()]
        return len(non_ascii_non_letter) > 0 and len(s.split()) <= 6

    # PASS 1: identify spell block boundary candidates
    # Each boundary = (name_line_idx, level_line_idx, level_int, school_str)
    # IMPORTANT: if the candidate name is junk, we do NOT jump forward -- we just
    # skip that line and keep scanning so the REAL spell name immediately after is captured.
    boundaries: list[tuple[int, int, int, str]] = []
    i = 0
    while i < len(all_lines):
        s = all_lines[i].strip()
        is_candidate = _is_spell_name_candidate(s)
        # Also accept garbled-name lines (non-ASCII) if directly followed by a level line
        is_garbled = not is_candidate and _is_garbled_name_before_level(s)
        if not is_candidate and not is_garbled:
            i += 1
            continue
        # look ahead up to 5 lines for level/cantrip marker
        found = False
        for j in range(i + 1, min(i + 6, len(all_lines))):
            sj = all_lines[j].strip()
            if not sj:
                continue
            lvl, school, is_cant = _parse_level_school(sj)
            if lvl is not None:
                # Check if this name is junk (regardless of garbled status,
                # _is_junk catches page numbers and captions with specific patterns)
                junk = _is_junk(s)
                if junk:
                    # Junk name found its level line -- but DON'T consume it.
                    # Just skip this one line so the next iteration picks up the
                    # real spell name that comes between this junk line and j.
                    i += 1
                elif is_garbled:
                    # Garbled but not junk: this is a real spell with OCR-mangled name
                    boundaries.append((i, j, lvl, school or "unknown"))
                    i = j + 1
                else:
                    boundaries.append((i, j, lvl, school or "unknown"))
                    i = j + 1
                found = True
                break
            # if we hit a field label before finding a level line, stop looking
            if re.match(r"(?i)^(Casting Time|Range|Components?|Duration):", sj):
                break
        if not found:
            i += 1

    spells: list[dict] = []
    for bi, (name_idx, lvl_idx, lvl, school) in enumerate(boundaries):
        raw_name = all_lines[name_idx].strip()
        # Sometimes the name spans two lines: "ARMS OF H ADAR" where one part is on prev line
        # If the line before name_idx is also caps and non-empty and no level line follows it,
        # it is part of the name -- but in practice the PDF puts the full name on one line.
        # Instead handle: name line + continuation on lvl_idx - 1 if that's different from name_idx+1
        if lvl_idx == name_idx + 2:
            mid = all_lines[name_idx + 1].strip()
            # Only merge if: mid is a valid candidate, not junk, AND
            # the primary name line doesn't end with a period (caption sentence ending)
            # and doesn't contain characters that spell names never have
            primary_is_clean = (
                not raw_name.rstrip().endswith(".")
                and not re.search(r"[/\\|{}<>@#%^~`'\"]", raw_name)
                and len(raw_name.split()) <= 4  # names only split at <= 4 words per line
            )
            if mid and _is_spell_name_candidate(mid) and not _is_junk(mid) and primary_is_clean:
                raw_name = (raw_name + " " + mid).strip()

        # Check raw key overrides first (handles OCR cases too garbled for fuzzy match)
        rk = _key(raw_name)
        if rk in RAW_KEY_OVERRIDES:
            name = RAW_KEY_OVERRIDES[rk]
            name_status = "fuzzy"
        else:
            name, name_status = _repair_spell_name(raw_name)

        # Body: from after the level line to the next boundary's name line
        body_start = lvl_idx + 1
        body_end = boundaries[bi + 1][0] if bi + 1 < len(boundaries) else len(all_lines)
        block_lines = all_lines[body_start:body_end]

        # Parse header fields (Casting Time / Range / Components / Duration)
        field_map: dict[str, str] = {}
        header_end = 0
        for li, raw in enumerate(block_lines[:14]):
            s = raw.strip()
            fm = re.match(r"(?i)^(Casting\s+Time|Range|Components?|Duration)\s*:\s*(.*)$", s)
            if fm:
                raw_key = fm.group(1).lower().replace(" ", "_")
                # Normalize "component" and "components" to "components"
                key = "components" if raw_key.startswith("component") else raw_key
                val = fm.group(2).strip()
                # Multi-line value: if this looks truncated (ends in comma/dash/letter)
                # and the next line is not a field label, append it
                li2 = li + 1
                while li2 < len(block_lines) and li2 < li + 4:
                    nxt = block_lines[li2].strip()
                    if not nxt:
                        break
                    if re.match(r"(?i)^(Casting\s+Time|Range|Components?|Duration)\s*:", nxt):
                        break
                    # it's a continuation (e.g. class list or wrapped casting time)
                    # Stop if this looks like body text (starts with uppercase word = sentence start)
                    # or if the current value is already complete (e.g. "Instantaneous", "1 hour")
                    val_seems_complete = bool(re.match(
                        r"(?i)(instantaneous|[0-9]+\s*(hour|minute|day|round)|until\s|special|concentration|[0-9]+\s+[a-z])",
                        val.strip()
                    ))
                    if val_seems_complete:
                        break
                    # Also stop if nxt looks like the start of body text (starts with capital word
                    # that is not a class name or field continuation)
                    if re.match(r"^[A-Z][a-z]+\s", nxt):  # "You ", "The ", "Choose ", etc.
                        break
                    val = val + " " + nxt
                    li2 += 1
                field_map[key] = val
                header_end = li + 1
            elif li > 2 and not s and field_map:
                break

        casting_time = field_map.get("casting_time", "").strip()
        range_ = field_map.get("range", "").strip()
        duration = field_map.get("duration", "").strip()
        components_raw = field_map.get("components", "").strip()

        concentration = bool(re.search(r"\bConcentration\b", duration, re.I))
        level_line_text = all_lines[lvl_idx]
        ritual = bool(
            re.search(r"\bRitual\b", casting_time, re.I)
            or re.search(r"\bRitual\b", level_line_text, re.I)
        )

        comps, material = _parse_components(components_raw)

        body_raw = "\n".join(block_lines[header_end:])
        higher_m = re.search(
            r"Using\s+a\s+Higher[- ]Level\s+Spell\s+Slot\.?\s*", body_raw, re.I
        )
        if higher_m:
            description = _clean(body_raw[: higher_m.start()])
            at_higher = _clean(body_raw[higher_m.end():])
        else:
            description = _clean(body_raw)
            at_higher = ""

        ocr_suspect = bool(OCR_JUNK.search(description) or OCR_JUNK.search(at_higher))

        rec: dict = {
            "index": _slug(name),
            "name": name,
            "level": lvl,
            "school": school or "unknown",
            "ritual": ritual,
            "concentration": concentration,
            "casting_time": _clean(casting_time),
            "range": _clean(range_),
            "duration": _clean(duration),
            "components": comps,
            "material": material,
            "description": description,
            "at_higher_levels": at_higher,
            "classes": [],
            "ocr_suspect": ocr_suspect,
            "srd": False,
            "local": True,
            "source": SOURCE,
        }

        if name_status == "fuzzy":
            rec["name_ocr_raw"] = raw_name
        elif name_status == "suspect":
            rec["name_ocr_raw"] = raw_name
            rec["name_ocr_suspect"] = True

        spells.append(rec)

    # De-duplicate by index (keep first occurrence)
    seen: set[str] = set()
    deduped: list[dict] = []
    for sp in spells:
        if sp["index"] not in seen:
            seen.add(sp["index"])
            deduped.append(sp)

    return deduped


# ── main ──────────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    if not argv:
        print("usage: extract_phb2024_spells.py <path-to-PHB-2024.pdf>", file=sys.stderr)
        return 2
    pdf = Path(argv[0])
    if not pdf.exists():
        print(f"not found: {pdf}", file=sys.stderr)
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf)
    spells = extract_spells(doc)

    out_path = OUT / "spells_2024_phb.json"
    out_path.write_text(
        json.dumps(spells, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    ocr_suspects = sum(1 for s in spells if s.get("ocr_suspect"))
    no_desc = [s["name"] for s in spells if not s.get("description")]
    bad_school = [s["name"] for s in spells if s["school"] == "unknown"]
    no_casting = [s["name"] for s in spells if not s.get("casting_time")]
    name_suspects = [s["name"] for s in spells if s.get("name_ocr_suspect")]
    name_fuzzy = [(s["name"], s.get("name_ocr_raw")) for s in spells if "name_ocr_raw" in s and not s.get("name_ocr_suspect")]

    print(f"Spells extracted:  {len(spells)}")
    print(f"OCR suspect:       {ocr_suspects}")
    if name_suspects:
        print(f"Name still suspect ({len(name_suspects)}): {name_suspects}")
    if name_fuzzy:
        print(f"Name auto-fixed ({len(name_fuzzy)}):")
        for good, raw in name_fuzzy[:10]:
            raw_safe = (raw or '').encode('ascii', 'replace').decode()
            print(f"  '{good}'  (raw: '{raw_safe}')")
    if no_desc:
        print(f"No description ({len(no_desc)}): {no_desc}")
    if bad_school:
        print(f"Unknown school ({len(bad_school)}): {bad_school}")
    if no_casting:
        print(f"No casting time ({len(no_casting)}): {no_casting}")
    print(f"Output: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
