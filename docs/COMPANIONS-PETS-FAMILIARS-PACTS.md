# Design note: companions · pets · familiars · warlock pacts

Captured 2026-06-21 (user request). Design/scoping for the "bonded creature" flavour + the linked-creation
springboard (HANDOVER §10 items 13 / 13b). **Not built yet** — this is the agreed shape to build to.

## 1. The four things and how they differ (D&D)
| Thing | What it is | Who has it | Combat? | Magic? |
|---|---|---|---|---|
| **Pet** | Pure flavour creature (cat, dog, rat). No real rules weight. | Anyone | No | No |
| **Companion** | A trained/bonded animal **ally that fights with you**. Usually a class feature — Ranger beast companion (Beast Master / Primal Companion), paladin's *Find Steed* mount, druid summons, Drakewarden, etc. | Mostly martial/nature (ranger esp.) | **Yes** | Sometimes (summoned) |
| **Familiar** | A **magical** creature summoned by *Find Familiar*. Animal shape but really a celestial/fey/fiend; tiny **scout/utility** (sees for you, delivers touch spells), not a brawler. | **Spellcasters only** | Rarely (a warlock Pact-of-the-Chain familiar can) | **Yes** |
| **Pact / Patron** | **Not a creature.** The warlock's bargain: who they serve (patron — Fiend, Archfey, Great Old One, Celestial, Undead, Genie…) + the **boon** they took. | Warlocks (patron/oath-bound classes have a lighter "who they serve") | — | Yes |

**The link:** a warlock's **Pact of the Chain** boon grants an (upgraded) **familiar** — so the pact element and
the familiar element connect for warlocks. (Other boons: Blade = a weapon, Tome = a book — not creatures.)

## 2. How each maps into our system (the 5 kinds stay fixed)
- **Companion** → kind `companion` (a real beast statblock that can fight; scales with / bonded to the owner).
- **Pet** → kind `pet` (Tiny/Small, minimal statblock, personality-led).
- **Familiar** → kind `pet` **flagged magical** (summoned; celestial/fey/fiend framing; caster-gated). Not a new kind.
- **Pact/Patron** → **a flavour element on the owning character, NOT a creation.** Influences story/look/powers;
  Pact of the Chain feeds the Familiar option.

## 3. Proposed UX
- **Player/NPC flavour** gains a **"Bonded creature"** row: a **type dropdown — None / Companion / Pet / Familiar**
  + a short free-text description (e.g. "Grey, a half-blind dire wolf who's never left her side"). Nudge: Familiar
  best suits casters (gate or hint when the owner doesn't cast).
- **Warlock "Pact & patron" pop-out** — appears when the class is (or could be) **warlock**: patron (Fiend / Archfey
  / Great Old One / Celestial / Undead / Genie / …) + boon (Chain / Blade / Tome). Chain → suggests a Familiar.
  Other patron/oath classes (paladin oath, cleric deity) get a lighter "who they serve" note, not a full pact panel.
- **Springboard (item 13b):** the chosen creature type sets the spawned kind — Companion→`companion`, Pet→`pet`,
  Familiar→`pet` (+magical framing, inherits the owner's caster/world context). The pair stay **linked**
  (owner↔creature ref; library shows "↳ <owner>'s companion/familiar").

## 4. Randomizer implications
- If the randomizer rolls a **warlock**, surface the pact/patron pop-out (roll a patron + boon for flavour).
- Familiar as a rolled "bonded creature" should be biased to **casters**; Companion biased to **rangers/martial**;
  Pet is universal.

## 5. Open questions to confirm before build
1. Dropdown set: **None / Companion / Pet / Familiar** — agreed?
2. Gate Familiar to casters (grey-out for non-casters) or just hint?
3. Warlock pact pop-out scope: patron + boon only for v1? Patron list — SRD ships **Fiend** only; the rest need the
   2024/PDF data (the data chats) — so v1 may be a free-text/short list until data lands.
4. Do paladins/clerics get a lighter "who they serve" note now, or later?
