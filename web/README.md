# Front-end ↔ engine integration

The front-end (Design's standalone HTML — Studio / Forge / Codex) talks to the local Flask
bridge through a thin adapter, **live-first with offline fallback**. The same file demos in the
design preview (fallback) and lights up with live data + real portraits against a running bridge.

## Files here
- `forge-bridge.js` — the adapter. Drop-in, no dependencies.
- `fallback-data.js` — bundled sample data (ruleset payloads + sample characters) for offline mode.
  Regenerate with `python scripts/build_fallback.py`.

## Wiring (Design adds to the prototype HTML)
```html
<script src="fallback-data.js"></script>
<script src="forge-bridge.js"></script>
<script>
  const forge = new ForgeBridge({
    // baseUrl defaults to http://localhost:5000 (persisted in localStorage; expose a field to change it)
    computePrompt: window.computePrompt,   // your existing canonical client-side prompt builder
    fallback: window.FORGE_FALLBACK,
  });

  // optional: show a "live" vs "preview (offline)" badge
  const live = await forge.isLive();

  // calls (all return the bridge shape live, or a graceful fallback offline):
  const { rulesets } = { rulesets: await forge.rulesets() };   // -> dropdown of rulesets
  const rs = await forge.ruleset("dnd5e-2014");                // -> labels + abilityRules + optionLists
  const { character, warnings } = await forge.forge(dump, { ruleset, kind });
  const prompt = await forge.artPreview(character, state);     // canonical when live; computePrompt() offline
  const { imageUrl, seed } = await forge.art(idOrCharacter, state, { tweak, seed });
  const list = await forge.characters();                       // starter rail
  const full = await forge.character(id);
  await forge.saveCharacter(character);
</script>
```

## Two modes (automatic)
- **Live:** HTML opened locally (`file://`) or served by Flask, pointed at a running bridge
  (`python -m forge.web.app`). Real `/forge`, real portraits, canonical `/art/preview`.
- **Fallback:** any time the bridge is unreachable (design preview, server down). Bundled samples
  populate dropdowns + rail; `computePrompt()` drives preview; portraits use the drop-slot.

## ⚠️ HTTPS can't reach http://localhost
An HTTPS page (e.g. GitHub Pages) is blocked from fetching `http://localhost:5000` (mixed
content), so a Pages-hosted copy stays in **fallback mode** — ideal for browsing/preview. For
**live** use, open the HTML locally or serve it from Flask (same origin). The adapter falls back
automatically, so nothing breaks either way.
