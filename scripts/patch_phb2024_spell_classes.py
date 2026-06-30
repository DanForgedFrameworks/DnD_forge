"""
patch_phb2024_spell_classes.py
-------------------------------
Patches data/local/spells_2024_phb.json with:
  1. classes[] field on all 370 spell records (from all 8 class spell lists)
  2. Two missing spells injected: Longstrider, Tasha's Hideous Laughter
  3. OCR-suspect body-text corrections from user-supplied screenshots:
       Minor Illusion, Blade Barrier, Greater Restoration, Greater Invisibility,
       Guardian of Faith, Disintegrate, Conjure Minor Elementals, Telepathy
Run from repo root:
  .venv_forge\\Scripts\\python.exe scripts/patch_phb2024_spell_classes.py
"""
import json, re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT   = Path(__file__).resolve().parent.parent
SPELLS = ROOT / "data" / "local" / "spells_2024_phb.json"
SOURCE = {"name": "Player's Handbook (2024)", "publisher": "Wizards of the Coast",
          "license": "All rights reserved (local prototyping only)"}

# ── helpers ───────────────────────────────────────────────────────────────────
def _slug(s):
    s = s.lower()
    s = re.sub(r"[''']", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")

# ── class spell lists (keyed class slug → flat spell-name list) ───────────────
CLASS_SPELLS = {
"bard": [
    # cantrips
    "Blade Ward","Dancing Lights","Friends","Light","Mage Hand","Mending","Message",
    "Minor Illusion","Prestidigitation","Starry Wisp","Thunderclap","True Strike","Vicious Mockery",
    # L1
    "Animal Friendship","Bane","Charm Person","Color Spray","Command","Comprehend Languages",
    "Cure Wounds","Detect Magic","Disguise Self","Dissonant Whispers","Faerie Fire","Feather Fall",
    "Healing Word","Heroism","Identify","Illusory Script","Longstrider","Silent Image","Sleep",
    "Speak with Animals","Tasha's Hideous Laughter","Thunderwave","Unseen Servant",
    # L2
    "Aid","Animal Messenger","Blindness/Deafness","Calm Emotions","Cloud of Daggers",
    "Crown of Madness","Detect Thoughts","Enhance Ability","Enlarge/Reduce","Enthrall",
    "Heat Metal","Hold Person","Invisibility","Knock","Lesser Restoration",
    "Locate Animals or Plants","Locate Object","Magic Mouth","Mirror Image","Phantasmal Force",
    "See Invisibility","Shatter","Silence","Suggestion","Zone of Truth",
    # L3
    "Bestow Curse","Clairvoyance","Dispel Magic","Fear","Feign Death","Glyph of Warding",
    "Hypnotic Pattern","Leomund's Tiny Hut","Major Image","Mass Healing Word","Nondetection",
    "Plant Growth","Sending","Slow","Speak with Dead","Speak with Plants","Stinking Cloud","Tongues",
    # L4
    "Charm Monster","Compulsion","Confusion","Dimension Door","Fount of Moonlight",
    "Freedom of Movement","Greater Invisibility","Hallucinatory Terrain","Locate Creature",
    "Phantasmal Killer","Polymorph",
    # L5
    "Animate Objects","Awaken","Dominate Person","Dream","Geas","Greater Restoration",
    "Hold Monster","Legend Lore","Mass Cure Wounds","Mislead","Modify Memory","Planar Binding",
    "Raise Dead","Rary's Telepathic Bond","Scrying","Seeming","Synaptic Static",
    "Teleportation Circle","Yolande's Regal Presence",
    # L6
    "Eyebite","Find the Path","Guards and Wards","Heroes' Feast","Mass Suggestion",
    "Otto's Irresistible Dance","Programmed Illusion","True Seeing",
    # L7
    "Etherealness","Forcecage","Mirage Arcane","Mordenkainen's Magnificent Mansion",
    "Mordenkainen's Sword","Power Word Fortify","Prismatic Spray","Project Image",
    "Regenerate","Resurrection","Symbol","Teleport",
    # L8
    "Antipathy/Sympathy","Befuddlement","Dominate Monster","Glibness","Mind Blank","Power Word Stun",
    # L9
    "Foresight","Power Word Heal","Power Word Kill","Prismatic Wall","True Polymorph",
],
"cleric": [
    # cantrips
    "Guidance","Light","Mending","Resistance","Sacred Flame","Spare the Dying",
    "Thaumaturgy","Toll the Dead","Word of Radiance",
    # L1
    "Bane","Bless","Command","Create or Destroy Water","Cure Wounds","Detect Evil and Good",
    "Detect Magic","Detect Poison and Disease","Guiding Bolt","Healing Word","Inflict Wounds",
    "Protection from Evil and Good","Purify Food and Drink","Sanctuary","Shield of Faith",
    # L2
    "Aid","Augury","Blindness/Deafness","Calm Emotions","Continual Flame","Enhance Ability",
    "Find Traps","Gentle Repose","Hold Person","Lesser Restoration","Locate Object",
    "Prayer of Healing","Protection from Poison","Silence","Spiritual Weapon","Warding Bond",
    "Zone of Truth",
    # L3
    "Animate Dead","Aura of Vitality","Beacon of Hope","Bestow Curse","Clairvoyance",
    "Create Food and Water","Daylight","Dispel Magic","Feign Death","Glyph of Warding",
    "Magic Circle","Mass Healing Word","Meld into Stone","Protection from Energy","Remove Curse",
    "Revivify","Sending","Speak with Dead","Spirit Guardians","Tongues","Water Walk",
    # L4
    "Aura of Life","Aura of Purity","Banishment","Control Water","Death Ward","Divination",
    "Freedom of Movement","Guardian of Faith","Locate Creature","Stone Shape",
    # L5
    "Circle of Power","Commune","Contagion","Dispel Evil and Good","Flame Strike","Geas",
    "Greater Restoration","Hallow","Insect Plague","Legend Lore","Mass Cure Wounds",
    "Planar Binding","Raise Dead","Scrying","Summon Celestial",
    # L6
    "Blade Barrier","Create Undead","Find the Path","Forbiddance","Harm","Heal",
    "Heroes' Feast","Planar Ally","Sunbeam","True Seeing","Word of Recall",
    # L7
    "Conjure Celestial","Divine Word","Etherealness","Fire Storm","Plane Shift",
    "Power Word Fortify","Regenerate","Resurrection","Symbol",
    # L8
    "Antimagic Field","Control Weather","Earthquake","Holy Aura","Sunburst",
    # L9
    "Astral Projection","Gate","Mass Heal","Power Word Heal","True Resurrection",
],
"druid": [
    # cantrips
    "Druidcraft","Elementalism","Guidance","Mending","Message","Poison Spray","Produce Flame",
    "Resistance","Shillelagh","Spare the Dying","Starry Wisp","Thorn Whip","Thunderclap",
    # L1
    "Animal Friendship","Charm Person","Create or Destroy Water","Cure Wounds","Detect Magic",
    "Detect Poison and Disease","Entangle","Faerie Fire","Fog Cloud","Goodberry","Healing Word",
    "Ice Knife","Jump","Longstrider","Protection from Evil and Good","Purify Food and Drink",
    "Speak with Animals","Thunderwave",
    # L2
    "Aid","Animal Messenger","Augury","Barkskin","Beast Sense","Continual Flame","Darkvision",
    "Enhance Ability","Enlarge/Reduce","Find Traps","Flame Blade","Flaming Sphere","Gust of Wind",
    "Heat Metal","Hold Person","Lesser Restoration","Locate Animals or Plants","Locate Object",
    "Moonbeam","Pass without Trace","Protection from Poison","Spike Growth","Summon Beast",
    # L3
    "Aura of Vitality","Call Lightning","Conjure Animals","Daylight","Dispel Magic",
    "Elemental Weapon","Feign Death","Meld into Stone","Plant Growth","Protection from Energy",
    "Revivify","Sleet Storm","Speak with Plants","Summon Fey","Water Breathing","Water Walk",
    "Wind Wall",
    # L4
    "Blight","Charm Monster","Confusion","Conjure Minor Elementals","Conjure Woodland Beings",
    "Control Water","Divination","Dominate Beast","Fire Shield","Fount of Moonlight",
    "Freedom of Movement","Giant Insect","Grasping Vine","Hallucinatory Terrain","Ice Storm",
    "Locate Creature","Polymorph","Stone Shape","Stoneskin","Summon Elemental","Wall of Fire",
    # L5
    "Antilife Shell","Awaken","Commune with Nature","Cone of Cold","Conjure Elemental",
    "Contagion","Geas","Greater Restoration","Insect Plague","Mass Cure Wounds","Planar Binding",
    "Reincarnate","Scrying","Tree Stride","Wall of Stone",
    # L6
    "Conjure Fey","Find the Path","Flesh to Stone","Heal","Heroes' Feast","Move Earth",
    "Sunbeam","Transport via Plants","Wall of Thorns","Wind Walk",
    # L7
    "Fire Storm","Mirage Arcane","Plane Shift","Regenerate","Reverse Gravity","Symbol",
    # L8
    "Animal Shapes","Antipathy/Sympathy","Befuddlement","Control Weather","Earthquake",
    "Incendiary Cloud","Sunburst","Tsunami",
    # L9
    "Foresight","Shapechange","Storm of Vengeance","True Resurrection",
],
"paladin": [
    # L1
    "Bless","Command","Compelled Duel","Cure Wounds","Detect Evil and Good","Detect Magic",
    "Detect Poison and Disease","Divine Favor","Divine Smite","Heroism",
    "Protection from Evil and Good","Purify Food and Drink","Searing Smite","Shield of Faith",
    "Thunderous Smite","Wrathful Smite",
    # L2
    "Aid","Find Steed","Gentle Repose","Lesser Restoration","Locate Object","Magic Weapon",
    "Prayer of Healing","Protection from Poison","Shining Smite","Warding Bond","Zone of Truth",
    # L3
    "Aura of Vitality","Blinding Smite","Create Food and Water","Crusader's Mantle","Daylight",
    "Dispel Magic","Elemental Weapon","Magic Circle","Remove Curse","Revivify",
    # L4
    "Aura of Life","Aura of Purity","Banishment","Death Ward","Locate Creature","Staggering Smite",
    # L5
    "Banishing Smite","Circle of Power","Destructive Wave","Dispel Evil and Good","Geas",
    "Greater Restoration","Raise Dead","Summon Celestial",
],
"ranger": [
    # L1
    "Alarm","Animal Friendship","Cure Wounds","Detect Magic","Detect Poison and Disease",
    "Ensnaring Strike","Entangle","Fog Cloud","Goodberry","Hail of Thorns","Hunter's Mark",
    "Jump","Longstrider","Speak with Animals",
    # L2
    "Aid","Animal Messenger","Barkskin","Beast Sense","Cordon of Arrows","Darkvision",
    "Enhance Ability","Find Traps","Gust of Wind","Lesser Restoration","Locate Animals or Plants",
    "Locate Object","Magic Weapon","Pass without Trace","Protection from Poison","Silence",
    "Spike Growth","Summon Beast",
    # L3
    "Conjure Animals","Conjure Barrage","Daylight","Dispel Magic","Elemental Weapon",
    "Lightning Arrow","Meld into Stone","Nondetection","Plant Growth","Protection from Energy",
    "Revivify","Speak with Plants","Summon Fey","Water Breathing","Water Walk","Wind Wall",
    # L4
    "Conjure Woodland Beings","Dominate Beast","Freedom of Movement","Grasping Vine",
    "Locate Creature","Stoneskin","Summon Elemental",
    # L5
    "Commune with Nature","Conjure Volley","Greater Restoration","Steel Wind Strike",
    "Swift Quiver","Tree Stride",
],
"sorcerer": [
    # cantrips
    "Acid Splash","Blade Ward","Chill Touch","Dancing Lights","Elementalism","Fire Bolt",
    "Friends","Light","Mage Hand","Mending","Message","Mind Sliver","Minor Illusion",
    "Poison Spray","Prestidigitation","Ray of Frost","Shocking Grasp","Sorcerous Burst",
    "Thunderclap","True Strike",
    # L1
    "Burning Hands","Charm Person","Chromatic Orb","Color Spray","Comprehend Languages",
    "Detect Magic","Disguise Self","Expeditious Retreat","False Life","Feather Fall",
    "Fog Cloud","Grease","Ice Knife","Jump","Mage Armor","Magic Missile","Ray of Sickness",
    "Shield","Silent Image","Sleep","Thunderwave","Witch Bolt",
    # L2
    "Alter Self","Arcane Vigor","Blindness/Deafness","Blur","Cloud of Daggers","Crown of Madness",
    "Darkness","Darkvision","Detect Thoughts","Dragon's Breath","Enhance Ability","Enlarge/Reduce",
    "Flame Blade","Flaming Sphere","Gust of Wind","Hold Person","Invisibility","Knock","Levitate",
    "Magic Weapon","Mind Spike","Mirror Image","Misty Step","Phantasmal Force","Scorching Ray",
    "See Invisibility","Shatter","Spider Climb","Suggestion","Web",
    # L3
    "Blink","Clairvoyance","Counterspell","Daylight","Dispel Magic","Fear","Fireball","Fly",
    "Gaseous Form","Haste","Hypnotic Pattern","Lightning Bolt","Major Image",
    "Protection from Energy","Sleet Storm","Slow","Stinking Cloud","Tongues","Vampiric Touch",
    "Water Breathing","Water Walk",
    # L4
    "Banishment","Blight","Charm Monster","Confusion","Dimension Door","Dominate Beast",
    "Fire Shield","Greater Invisibility","Ice Storm","Polymorph","Stoneskin","Vitriolic Sphere",
    "Wall of Fire",
    # L5
    "Animate Objects","Bigby's Hand","Cloudkill","Cone of Cold","Creation","Dominate Person",
    "Hold Monster","Insect Plague","Seeming","Synaptic Static","Telekinesis","Teleportation Circle",
    "Wall of Stone",
    # L6
    "Arcane Gate","Chain Lightning","Circle of Death","Disintegrate","Eyebite","Flesh to Stone",
    "Globe of Invulnerability","Mass Suggestion","Move Earth","Otiluke's Freezing Sphere",
    "Sunbeam","True Seeing",
    # L7
    "Delayed Blast Fireball","Etherealness","Finger of Death","Fire Storm","Plane Shift",
    "Prismatic Spray","Reverse Gravity","Teleport",
    # L8
    "Demiplane","Dominate Monster","Earthquake","Incendiary Cloud","Power Word Stun","Sunburst",
    # L9
    "Gate","Meteor Swarm","Power Word Kill","Time Stop","Wish",
],
"warlock": [
    # cantrips
    "Blade Ward","Chill Touch","Eldritch Blast","Friends","Mage Hand","Mind Sliver",
    "Minor Illusion","Poison Spray","Prestidigitation","Thunderclap","Toll the Dead","True Strike",
    # L1
    "Armor of Agathys","Arms of Hadar","Bane","Charm Person","Comprehend Languages",
    "Detect Magic","Expeditious Retreat","Hellish Rebuke","Hex","Illusory Script",
    "Protection from Evil and Good","Speak with Animals","Tasha's Hideous Laughter",
    "Unseen Servant","Witch Bolt",
    # L2
    "Cloud of Daggers","Crown of Madness","Darkness","Enthrall","Hold Person","Invisibility",
    "Mind Spike","Mirror Image","Misty Step","Ray of Enfeeblement","Spider Climb","Suggestion",
    # L3
    "Counterspell","Dispel Magic","Fear","Fly","Gaseous Form","Hunger of Hadar",
    "Hypnotic Pattern","Magic Circle","Major Image","Remove Curse","Summon Fey","Summon Undead",
    "Tongues","Vampiric Touch",
    # L4
    "Banishment","Blight","Charm Monster","Dimension Door","Hallucinatory Terrain","Summon Aberration",
    # L5
    "Contact Other Plane","Dream","Hold Monster","Jallarzi's Storm of Radiance","Mislead",
    "Planar Binding","Scrying","Synaptic Static","Teleportation Circle",
    # L6
    "Arcane Gate","Circle of Death","Create Undead","Eyebite","Summon Fiend",
    "Tasha's Bubbling Cauldron","True Seeing",
    # L7
    "Etherealness","Finger of Death","Forcecage","Plane Shift",
    # L8
    "Befuddlement","Demiplane","Dominate Monster","Glibness","Power Word Stun",
    # L9
    "Astral Projection","Foresight","Gate","Imprisonment","Power Word Kill","True Polymorph","Weird",
],
"wizard": [
    # cantrips
    "Acid Splash","Blade Ward","Chill Touch","Dancing Lights","Elementalism","Fire Bolt",
    "Friends","Light","Mage Hand","Mending","Message","Mind Sliver","Minor Illusion",
    "Poison Spray","Prestidigitation","Ray of Frost","Shocking Grasp","Thunderclap",
    "Toll the Dead","True Strike",
    # L1
    "Alarm","Burning Hands","Charm Person","Chromatic Orb","Color Spray","Comprehend Languages",
    "Detect Magic","Disguise Self","Expeditious Retreat","False Life","Feather Fall",
    "Find Familiar","Fog Cloud","Grease","Ice Knife","Identify","Illusory Script","Jump",
    "Longstrider","Mage Armor","Magic Missile","Protection from Evil and Good","Ray of Sickness",
    "Shield","Silent Image","Sleep","Tasha's Hideous Laughter","Tenser's Floating Disk",
    "Thunderwave","Unseen Servant","Witch Bolt",
    # L2
    "Alter Self","Arcane Lock","Arcane Vigor","Augury","Blindness/Deafness","Blur",
    "Cloud of Daggers","Continual Flame","Crown of Madness","Darkness","Darkvision",
    "Detect Thoughts","Dragon's Breath","Enhance Ability","Enlarge/Reduce","Flaming Sphere",
    "Gentle Repose","Gust of Wind","Hold Person","Invisibility","Knock","Levitate",
    "Locate Object","Magic Mouth","Magic Weapon","Melf's Acid Arrow","Mind Spike","Mirror Image",
    "Misty Step","Nystul's Magic Aura","Phantasmal Force","Ray of Enfeeblement","Rope Trick",
    "Scorching Ray","See Invisibility","Shatter","Spider Climb","Suggestion","Web",
    # L3
    "Animate Dead","Bestow Curse","Blink","Clairvoyance","Counterspell","Dispel Magic",
    "Fear","Feign Death","Fireball","Fly","Gaseous Form","Glyph of Warding","Haste",
    "Hypnotic Pattern","Leomund's Tiny Hut","Lightning Bolt","Magic Circle","Major Image",
    "Nondetection","Phantom Steed","Protection from Energy","Remove Curse","Sending",
    "Sleet Storm","Slow","Speak with Dead","Stinking Cloud","Summon Fey","Summon Undead",
    "Tongues","Vampiric Touch","Water Breathing",
    # L4
    "Arcane Eye","Banishment","Blight","Charm Monster","Confusion","Conjure Minor Elementals",
    "Control Water","Dimension Door","Divination","Evard's Black Tentacles","Fabricate",
    "Fire Shield","Greater Invisibility","Hallucinatory Terrain","Ice Storm",
    "Leomund's Secret Chest","Locate Creature","Mordenkainen's Faithful Hound",
    "Mordenkainen's Private Sanctum","Otiluke's Resilient Sphere","Phantasmal Killer",
    "Polymorph","Stone Shape","Stoneskin","Summon Aberration","Summon Construct",
    "Summon Elemental","Vitriolic Sphere","Wall of Fire",
    # L5
    "Animate Objects","Bigby's Hand","Circle of Power","Cloudkill","Cone of Cold",
    "Conjure Elemental","Contact Other Plane","Creation","Dominate Person","Dream","Geas",
    "Hold Monster","Jallarzi's Storm of Radiance","Legend Lore","Mislead","Modify Memory",
    "Passwall","Planar Binding","Rary's Telepathic Bond","Scrying","Seeming","Steel Wind Strike",
    "Summon Dragon","Synaptic Static","Telekinesis","Teleportation Circle","Wall of Force",
    "Wall of Stone","Yolande's Regal Presence",
    # L6
    "Arcane Gate","Chain Lightning","Circle of Death","Contingency","Create Undead",
    "Disintegrate","Drawmij's Instant Summons","Eyebite","Flesh to Stone",
    "Globe of Invulnerability","Guards and Wards","Magic Jar","Mass Suggestion","Move Earth",
    "Otiluke's Freezing Sphere","Otto's Irresistible Dance","Programmed Illusion","Summon Fiend",
    "Sunbeam","Tasha's Bubbling Cauldron","True Seeing","Wall of Ice",
    # L7
    "Delayed Blast Fireball","Etherealness","Finger of Death","Forcecage","Mirage Arcane",
    "Mordenkainen's Magnificent Mansion","Mordenkainen's Sword","Plane Shift","Prismatic Spray",
    "Project Image","Reverse Gravity","Sequester","Simulacrum","Symbol","Teleport",
    # L8
    "Antimagic Field","Antipathy/Sympathy","Befuddlement","Clone","Control Weather","Demiplane",
    "Dominate Monster","Incendiary Cloud","Maze","Mind Blank","Power Word Stun","Sunburst",
    "Telepathy",
    # L9
    "Astral Projection","Foresight","Gate","Imprisonment","Meteor Swarm","Power Word Kill",
    "Prismatic Wall","Shapechange","Time Stop","True Polymorph","Weird","Wish",
],
}

# ── build reverse map: slug(name) → [class slugs] ────────────────────────────
spell_to_classes: dict[str, list[str]] = {}
for cls, names in CLASS_SPELLS.items():
    for name in names:
        key = _slug(name)
        spell_to_classes.setdefault(key, [])
        if cls not in spell_to_classes[key]:
            spell_to_classes[key].append(cls)

# ── OCR body-text corrections (from user screenshots) ─────────────────────────
BODY_FIXES = {
    "minor-illusion": {
        "description": (
            "You create a sound or an image of an object within range that lasts for the duration. "
            "See the descriptions below for the effects of each. The illusion ends if you cast this spell again.\n"
            "If a creature takes a Study action to examine the sound or image, the creature can determine "
            "that it is an illusion with a successful Intelligence (Investigation) check against your spell "
            "save DC. If a creature discerns the illusion for what it is, the illusion becomes faint to the creature."
        ),
    },
    "blade-barrier": {
        "description": (
            "You create a wall of whirling blades made of magical energy. The wall appears within range and "
            "lasts for the duration. You make a straight wall up to 100 feet long, 20 feet high, and 5 feet "
            "thick, or a ringed wall up to 60 feet in diameter, 20 feet high, and 5 feet thick. The wall "
            "provides Three-Quarters Cover, and its space is Difficult Terrain.\n"
            "Any creature in the wall's space makes a Dexterity saving throw, taking 6d10 Force damage on a "
            "failed save or half as much damage on a successful one. A creature also makes that save if it "
            "enters the wall's space or ends its turn there. A creature makes that save only once per turn."
        ),
    },
    "greater-invisibility": {
        "description": "A creature you touch has the Invisible condition until the spell ends.",
    },
    "greater-restoration": {
        "description": (
            "You touch a creature and magically remove one of the following effects from it:\n"
            "• 1 Exhaustion level\n"
            "• The Charmed or Petrified condition\n"
            "• A curse, including the target's Attunement to a cursed magic item\n"
            "• Any reduction to one of the target's ability scores\n"
            "• Any reduction to the target's Hit Point maximum"
        ),
    },
    "guardian-of-faith": {
        "description": (
            "A Large spectral guardian appears and hovers for the duration in an unoccupied space that you "
            "can see within range. The guardian occupies that space and is invulnerable, and it appears in "
            "a form appropriate for your deity or pantheon.\n"
            "Any enemy that moves to a space within 10 feet of the guardian for the first time on a turn or "
            "starts its turn there makes a Dexterity saving throw, taking 20 Radiant damage on a failed save "
            "or half as much damage on a successful one. The guardian vanishes when it has dealt a total of "
            "60 damage."
        ),
    },
    "disintegrate": {
        "description": (
            "You launch a green ray at a target you can see within range. The target can be a creature, a "
            "nonmagical object, or a creation of magical force, such as the wall created by Wall of Force.\n"
            "A creature targeted by this spell makes a Dexterity saving throw. On a failed save, the target "
            "takes 10d6 + 40 Force damage. If this damage reduces it to 0 Hit Points, it and everything "
            "nonmagical it is wearing and carrying are disintegrated into gray dust. The target can be "
            "revived only by a True Resurrection or a Wish spell.\n"
            "This spell automatically disintegrates a Large or smaller nonmagical object or a creation of "
            "magical force. If such a target is Huge or larger, this spell disintegrates a 10-foot-Cube "
            "portion of it."
        ),
        "at_higher_levels": "The damage increases by 3d6 for each spell slot level above 6.",
    },
    "conjure-minor-elementals": {
        "description": (
            "You conjure spirits from the Elemental Planes that flit around you in a 15-foot Emanation for "
            "the duration. Until the spell ends, any attack you make deals an extra 2d8 damage when you hit "
            "a creature in the Emanation. This damage is Acid, Cold, Fire, or Lightning (your choice when "
            "you make the attack).\n"
            "In addition, the ground in the Emanation is Difficult Terrain for your enemies."
        ),
        "at_higher_levels": "The damage increases by 2d8 for each spell slot level above 4.",
    },
    "telepathy": {
        "components": ["V", "S", "M"],
        "material": "a pair of linked silver rings",
        "description": (
            "You create a telepathic link between yourself and a willing creature with which you are familiar. "
            "The creature can be anywhere on the same plane of existence as you. The spell ends if you or "
            "the target are no longer on the same plane.\n"
            "Until the spell ends, you and the target can instantly share words, images, sounds, and other "
            "sensory messages with each other through the link, and the target recognizes you as the creature "
            "it is communicating with. The spell enables the creature to understand the meaning of your words "
            "and any sensory messages you send to it."
        ),
    },
}

# ── missing spells to inject ──────────────────────────────────────────────────
NEW_SPELLS = [
    {
        "index": "longstrider",
        "name": "Longstrider",
        "level": 1,
        "school": "transmutation",
        "ritual": False,
        "concentration": False,
        "casting_time": "Action",
        "range": "Touch",
        "duration": "1 hour",
        "components": ["V", "S", "M"],
        "material": "a pinch of dirt",
        "description": (
            "You touch a creature. The target's Speed increases by 10 feet until the spell ends."
        ),
        "at_higher_levels": "You can target one additional creature for each spell slot level above 1.",
        "classes": ["bard", "druid", "ranger", "wizard"],
        "ocr_suspect": False,
        "srd": False, "local": True, "source": SOURCE,
    },
    {
        "index": "tashas-hideous-laughter",
        "name": "Tasha's Hideous Laughter",
        "level": 1,
        "school": "enchantment",
        "ritual": False,
        "concentration": True,
        "casting_time": "Action",
        "range": "30 feet",
        "duration": "Concentration, up to 1 minute",
        "components": ["V", "S", "M"],
        "material": "a tart and a feather",
        "description": (
            "One creature of your choice that you can see within range makes a Wisdom saving throw. "
            "On a failed save, it has the Prone and Incapacitated conditions for the duration. During "
            "that time, it laughs uncontrollably if it's capable of laughter, and it can't end the "
            "Prone condition on itself.\n"
            "At the end of each of its turns and each time it takes damage, it makes another Wisdom "
            "saving throw. The target has Advantage on the save if the save is triggered by damage. "
            "On a successful save, the spell ends."
        ),
        "at_higher_levels": "You can target one additional creature for each spell slot level above 1.",
        "classes": ["bard", "warlock", "wizard"],
        "ocr_suspect": False,
        "srd": False, "local": True, "source": SOURCE,
    },
]

# ── main ──────────────────────────────────────────────────────────────────────
def main():
    spells = json.loads(SPELLS.read_text(encoding="utf-8"))
    print(f"Loaded {len(spells)} spells")

    # 1) inject missing spells (skip if already present by index)
    existing_indices = {s["index"] for s in spells}
    injected = 0
    for ns in NEW_SPELLS:
        if ns["index"] not in existing_indices:
            spells.append(ns)
            existing_indices.add(ns["index"])
            injected += 1
            print(f"  + Injected: {ns['name']}")
        else:
            print(f"  ~ Already present: {ns['name']}")

    # 2) sort by level then name
    spells.sort(key=lambda s: (s.get("level", 0), s.get("name", "")))

    # 3) patch classes + body fixes
    classes_patched = 0
    body_patched    = 0
    not_matched     = []

    for spell in spells:
        key = _slug(spell.get("name", ""))

        # classes
        cls_list = sorted(spell_to_classes.get(key, []))
        if cls_list:
            spell["classes"] = cls_list
            classes_patched += 1
        else:
            not_matched.append(spell["name"])

        # body fixes
        if key in BODY_FIXES:
            for field, val in BODY_FIXES[key].items():
                spell[field] = val
            spell["ocr_suspect"] = False
            spell.pop("desc_source", None)
            body_patched += 1

    # 4) write back
    SPELLS.write_text(json.dumps(spells, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nDone.")
    print(f"  Total spells : {len(spells)}")
    print(f"  Injected     : {injected}")
    print(f"  Classes set  : {classes_patched}")
    print(f"  Body fixed   : {body_patched}")
    if not_matched:
        print(f"  No class match ({len(not_matched)}): {', '.join(not_matched[:20])}")
        if len(not_matched) > 20:
            print(f"    ... and {len(not_matched)-20} more")

if __name__ == "__main__":
    main()
