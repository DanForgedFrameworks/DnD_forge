# Character Forge — front-end handover

Drop these four files in one folder. They run as-is.

## Files
- **Claude Code - Engine Handoff.md** — the full contract (schema §1, maths §2, prompts, Flask bridge §5.1–5.2). Source of truth.
- **Character Forge - Prototype.dc.html** — the front-end (Studio / Forge / Codex). Open it directly in a browser.
- **support.js** — the DC runtime it loads (`./support.js`). Must sit beside the HTML.
- **image-slot.js** — the drag-drop portrait fallback component (`./image-slot.js`). Must sit beside the HTML.

## Running it
1. Keep all four files in the same folder.
2. Open `Character Forge - Prototype.dc.html` in a browser (double-click / `file://`).
3. It boots in **Local preview** mode (top-right pill) using built-in sample creatures — no server needed.
4. Start the bridge (`python -m forge.web.app`, default `http://localhost:5000`). Reload the page: the pill flips to **Bridge live** and it wires up rulesets, forge, the starter rail, and live portraits.

## Pointing at a non-default bridge
- `localStorage.setItem('forgeBridgeUrl','http://localhost:5001')`, or
- open with `?bridge=http://localhost:5001`.

The probe only fires from a `file://` / localhost / override context, so a cloud-hosted copy stays in safe fallback. If you ever serve this HTML from a non-localhost https origin, the browser blocks `http://localhost` as mixed content — serve the bridge over https or serve the HTML from Flask in that case.

## What the front-end expects from the bridge
See §5.2 of the handoff doc. Quick list of the nine endpoints:
`GET /rulesets` · `GET /ruleset/<slug>` · `POST /forge` · `POST /art/preview` · `POST /art` · `GET /character` · `GET /character/<id>` · `POST /character` · `GET /art/<id>/<state>.png`
