"""Equipment catalog + name canonicalisation (the gear-resolution layer).

The forge builds gear from each class's/background's ``starting_equipment`` and, in
relaxed mode, from the AI's free-written list. Neither path knows about the global
equipment table or the ``_homebrew`` overlay, so iconic species items (the kender
**Hoopak**) get either wiped (strict) or decomposed into their most legible component
(relaxed: a plain "Sling" + bullets). This module is the missing consumer:

- :func:`equipment_catalog` — every item the picker can offer (SRD + homebrew), as a
  flat ``{index, name, category, homebrew, modes?}`` list, optionally filtered by query.
- :func:`canonical_item` — map a free-text name (or a known alias) back to its catalog
  entry, so "kender hoopak" / "forked staff" resolve to the one real Hoopak.
- :func:`resolve_gear` — run over a PC's ``pc.equipment`` to (a) re-attach catalog data
  (modes, homebrew flag) to items named after a catalog entry, and (b) conservatively
  recombine a species signature item the AI split apart (kender Sling+bullets -> Hoopak).

Everything here is edition-aware and reads through :class:`SRDRepository`, so the
homebrew overlay is picked up exactly as ``tests/test_homebrew_overlay.py`` proves.
"""
from __future__ import annotations

import re
from functools import lru_cache

from ..canon import SRDRepository


@lru_cache(maxsize=4)
def _repo(edition: str = "2014") -> SRDRepository:
    return SRDRepository(edition)


# -- aliases: free-text name (lower-cased) -> canonical catalog index -----------
# Keyed for the kender Hoopak today; the table is the general place to teach the
# forge that other species signature items map back to one canonical entry.
_ALIASES: dict[str, str] = {
    "hoopak": "hoopak",
    "kender hoopak": "hoopak",
    "hoopak staff": "hoopak",
    "hoopak (sling)": "hoopak",
    "hoopak sling": "hoopak",
    "forked staff": "hoopak",
    "kender sling": "hoopak",
    "kender's hoopak": "hoopak",
}


def _category_of(entry: dict) -> str:
    """Human category for an equipment entry, across the 2014 (singular) and 2024 /
    homebrew (plural list) shapes."""
    cat = entry.get("equipment_category")
    if isinstance(cat, dict) and cat.get("name"):
        return cat["name"]
    cats = entry.get("equipment_categories")
    if isinstance(cats, list) and cats:
        return cats[0].get("name", "") if isinstance(cats[0], dict) else str(cats[0])
    return ""


def _modes_of(entry: dict) -> list[dict] | None:
    """Structured use-modes for a multi-mode item (e.g. the Hoopak's staff/sling/
    bullroarer). Read straight from the catalog entry's ``modes`` when present;
    None for ordinary single-profile items."""
    modes = entry.get("modes")
    return modes if isinstance(modes, list) and modes else None


def _catalog_card(entry: dict) -> dict:
    """The compact item shape the picker + saved characters use."""
    card = {
        "index": entry.get("index") or entry.get("name"),
        "name": entry.get("name"),
        "category": _category_of(entry),
    }
    if entry.get("homebrew"):
        card["homebrew"] = True
    modes = _modes_of(entry)
    if modes:
        card["modes"] = modes
    ammo = entry.get("ammunition")
    if isinstance(ammo, dict) and ammo.get("name"):
        card["ammunition"] = ammo["name"]
    return card


def equipment_catalog(edition: str = "2014", query: str | None = None) -> list[dict]:
    """All equipment items (SRD + homebrew overlay) as picker cards, optionally
    filtered by a case-insensitive substring ``query`` over name/category.

    Sorted homebrew-first then alphabetically, so species signature items surface
    at the top of an empty search.
    """
    try:
        entries = _repo(edition).all("equipment")
    except Exception:
        return []
    cards = [_catalog_card(e) for e in entries if e.get("name")]
    q = (query or "").strip().lower()
    if q:
        cards = [c for c in cards
                 if q in (c["name"] or "").lower() or q in (c.get("category") or "").lower()]
    cards.sort(key=lambda c: (0 if c.get("homebrew") else 1, (c["name"] or "").lower()))
    return cards


def canonical_item(name: str, edition: str = "2014") -> dict | None:
    """Resolve a free-text item name (or a known alias) to its catalog card, else None.

    Tries, in order: the alias table, an exact index/name hit in the catalog. Plain
    items (e.g. "Dagger") resolve to themselves; unknown free text returns None so the
    caller can leave it untouched.
    """
    key = (name or "").strip().lower()
    if not key:
        return None
    target = _ALIASES.get(key)
    entry = _repo(edition).get("equipment", target) if target else None
    if entry is None:
        # direct match over a normalised key, so AI free-text resolves to the SRD entry:
        # the SRD inverts some names ("Crossbow, Light" vs a player's "Light Crossbow") and
        # punctuates differently, so compare on a word-set that ignores order/commas/hyphens.
        want = _match_key(key)
        for e in _repo(edition).all("equipment"):
            if _match_key(e.get("index") or "") == want or _match_key(e.get("name") or "") == want:
                entry = e
                break
    return _catalog_card(entry) if entry else None


def _match_key(s: str) -> frozenset:
    """Order/punctuation-insensitive word set for loose name matching
    ('Crossbow, Light' and 'Light Crossbow' -> the same key)."""
    return frozenset(w for w in re.split(r"[\s,_\-]+", (s or "").lower()) if w)


def _is_sling(name: str) -> bool:
    n = (name or "").strip().lower()
    return n in ("sling", "a sling") or n.startswith("sling ") and "bullet" not in n


def _is_sling_ammo(name: str) -> bool:
    n = (name or "").strip().lower()
    return "sling" in n and "bullet" in n or n in ("bullets", "stones")


def resolve_gear(character: dict, edition: str = "2014") -> list[dict]:
    """Canonicalise a PC's equipment in place; return info-level warnings.

    Two passes, both conservative:

    1. **Re-attach catalog data.** Any item whose name matches a catalog entry or alias
       gets its canonical name + ``modes``/``homebrew`` re-attached (so a relaxed-mode
       "Hoopak" line gains its three modes; a "kender hoopak" line is renamed to "Hoopak").

    2. **Recombine a split signature item.** If the character is a kender and the AI split
       the Hoopak into a plain Sling (+ bullets) with no Hoopak present, fold the Sling
       back into one Hoopak and relabel the bullets as its ammunition. Gated tightly on
       species so an ordinary sling on a non-kender is never touched.
    """
    pc = character.get("pc")
    if not isinstance(pc, dict):
        return []
    items = pc.get("equipment")
    if not isinstance(items, list) or not items:
        return []

    out: list[dict] = []
    warnings: list[dict] = []

    # pass 1 — re-attach catalog data by name/alias
    canon_names = set()
    for it in items:
        if not isinstance(it, dict):
            it = {"name": str(it)}
        orig = it.get("name", "")
        card = canonical_item(orig, edition)
        if card:
            # Only RENAME for a genuine alias/homebrew item (e.g. "kender hoopak" -> "Hoopak").
            # A loose SRD match (e.g. "Light Crossbow" -> "Crossbow, Light") keeps the player's
            # wording — we attach data, we don't correct their spelling.
            is_alias = orig.strip().lower() in _ALIASES or bool(card.get("homebrew"))
            merged = dict(it)
            renamed = False
            if is_alias and card["name"] != orig:
                merged["name"] = card["name"]
                renamed = True
            if card.get("modes") and not merged.get("modes"):
                merged["modes"] = card["modes"]
            if card.get("homebrew"):
                merged["homebrew"] = True
            if card.get("ammunition") and not merged.get("ammunition"):
                merged["ammunition"] = card["ammunition"]
            out.append(merged)
            canon_names.add(merged["name"])
            if renamed:
                warnings.append({"level": "info",
                                 "message": f"matched '{orig}' to the catalog item '{card['name']}'"})
            elif card.get("modes"):
                warnings.append({"level": "info",
                                 "message": f"'{merged['name']}' kept as one item with {len(card['modes'])} modes"})
        else:
            out.append(it if isinstance(it, dict) else {"name": str(it)})

    # pass 2 — kender Hoopak recombine (only if no Hoopak already resolved)
    species = " ".join(str(pc.get(k) or "") for k in ("species", "subspecies")).lower()
    if "kender" in species and "Hoopak" not in canon_names:
        sling_i = next((i for i, it in enumerate(out) if _is_sling(it.get("name", ""))), None)
        if sling_i is not None:
            hoopak = canonical_item("hoopak", edition)
            if hoopak:
                merged = {"name": hoopak["name"]}
                if hoopak.get("modes"):
                    merged["modes"] = hoopak["modes"]
                if hoopak.get("homebrew"):
                    merged["homebrew"] = True
                if hoopak.get("ammunition"):
                    merged["ammunition"] = hoopak["ammunition"]
                out[sling_i] = merged
                # relabel a lone bullets entry as the Hoopak's ammunition (keep its qty)
                for it in out:
                    if _is_sling_ammo(it.get("name", "")) and "hoopak" not in it.get("name", "").lower():
                        it["name"] = "Sling bullets (Hoopak ammunition)"
                warnings.append({"level": "info",
                                 "message": "recombined the kender's Sling into a single Hoopak (staff / sling / bullroarer)"})

    pc["equipment"] = out
    return warnings
