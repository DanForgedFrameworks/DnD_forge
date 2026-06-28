# Brief: from-sheet ingestion — upload a Word/PDF (or paste) → AI draft character

**This is a self-contained task brief for a dedicated chat.** You do not need the rest of the project's
conversation history. Read top to bottom, confirm §8, then build §5. Your job is **back-end + a
text-extraction helper + one bridge endpoint** — you are reusing the existing AI brain, not building a
new one, and you are **NOT editing the front-end** (see §7).

---

## 1. What this project is (one paragraph)
The **D&D Character Forge** (repo root: `C:\Users\celt_\OneDrive\VLE e-Learning Documents\D&D Character Forge`,
GitHub `DanForgedFrameworks/DnD_forge`) is a local Flask + Python tool that turns a description into a
rules-legal D&D 5e character sheet + portrait. Principle: **agents propose, the engine disposes** — an LLM
picks choices + prose, deterministic Python computes/validates the numbers. There's already a "forge from a
sentence" path (brain-dump → AI → `Character` JSON). This task adds **"forge from an existing sheet"**:
upload a Word/PDF (or paste the text), the AI reads it into a draft character, and the user fixes the last
bit in the Studio.

## 2. The mission
Let a user bring an **existing** character in with near-zero friction: **upload a `.docx`/`.pdf` (or paste
text) → extract the text → feed it to the existing auto-fill agent → return a `Character` (+ warnings),
same shape the front-end already consumes.** The AI gives a strong *draft*; the engine validates; the user
corrects the rest in the Studio. Do **not** chase a perfect parse.

## 3. Decisions already made (do not re-litigate)
- **Approach = AI-assisted upload (v1).** Reuse the existing agent; don't write a new parser.
- **The deterministic structured-template path (a filled spreadsheet/CSV → exact parser, no AI) is a
  SEPARATE, LATER chat — not in scope here.** Mention-only.
- **Result lands in the Studio for correction** (the app's existing "good draft, then tidy" grain).
- **Do NOT edit the front-end file** (`web/frontend/Character Forge - Prototype.dc.html`) — it's mid-edit
  and serialized to the main build chat. You deliver the back-end + a documented request/response contract
  (§7); the build chat wires the actual file input.

## 4. What already exists (reuse this — don't rebuild)
- `forge/agents/autofill.py` → `autofill(brain_dump, *, ruleset, kind, rules_mode, details, docx_text)`
  **already accepts `docx_text`** and folds it into the prompt for BOTH the monster and PC paths. Returns
  `{"character": <Character>, "warnings": [...]}`.
- `forge/web/app.py` → `POST /forge` already calls `autofill(...)` and returns `{character, warnings}`, but
  it currently passes only `dump/ruleset/kind/rulesMode/details` — **not** `docx_text`. It also logs every
  call via `log_forge(...)`. Mirror that handler.
- **`python-docx` is already a dependency** (`requirements.txt`). **PDF extraction is NOT yet available** —
  add a pure-Python lib (`pypdf>=4`; no system deps). This is the only new dependency in scope.
- Run/test: venv = `.venv_forge/Scripts/python.exe`; bridge = `python -m forge.web.app` → `:5000`.

## 5. The deliverable — three pieces
**(a) Text-extraction helper** (suggest `forge/agents/sheet_extract.py`):
`extract_sheet_text(filename, data: bytes) -> str` — dispatch by extension: `.docx` via `python-docx`
(join paragraphs + table cells), `.pdf` via `pypdf` (concatenate `page.extract_text()`), `.txt`/`.md`
pass-through. Raise a clear error for unsupported types. **Scanned/image-only PDFs (no text layer) → OCR is
OUT of scope v1**; detect "no text extracted" and return a warning the endpoint surfaces.

**(b) Bridge endpoint** `POST /forge/sheet` (multipart/form-data), in `forge/web/app.py`:
- Read the uploaded file from `request.files["file"]`; optional form fields `ruleset`, `kind`
  (default `"character"` — a sheet is almost always a PC), `rulesMode` (default `"relaxed"`).
- `text = extract_sheet_text(file.filename, file.read())`. If empty → return a JSON warning
  (`{"error":"no_text", "message":"Couldn't read text from that file (a scanned image PDF?)."}`, 422).
- Call `autofill("", ruleset=ruleset, kind=kind, rules_mode=rulesMode, docx_text=text)`.
- Return `jsonify(result)` — **identical `{character, warnings:[{level,message}]}` shape as `/forge`** so the
  front-end reuses its existing landing logic. Wrap in the same try/except + `log_forge` as `/forge`
  (surface provider errors as JSON 502, not a 500 page). Keep the permissive CORS (`_cors`).

**(c) The front-end contract** (document only — do NOT implement): a `<input type="file">` that POSTs
`multipart/form-data` with field `file` (+ optional `ruleset`/`kind`) to `/forge/sheet`, then lands
`res.character` into the draft and switches to the Studio — exactly as `forgeViaBridge()` does with `/forge`
today. Write this contract into the brief's hand-back note so the build chat can wire it in minutes.

## 6. Acceptance tests
- **Assembly (no API):** monkeypatch the model call (as the existing autofill tests do) and feed a sample
  sheet's text → assert `kind=="character"`, `pc{}` populated, `{character, warnings}` shape. Add a tiny
  fixture `.docx` (or reuse `samples/`) for the extraction helper.
- **Live (behind the key):** a real `.docx`/`.pdf` of a PC → a sensible draft character.
- Extraction unit tests: docx text, pdf text, and the "no text" path each behave.

## 7. Don'ts
- Don't edit `web/frontend/Character Forge - Prototype.dc.html` (front-end is serialized elsewhere).
- Don't build the spreadsheet/CSV template + deterministic parser (separate later chat).
- Don't change `autofill`'s core logic — only call it with `docx_text`.

## 8. Inputs to confirm before starting
1. Bridge runs green: `.venv_forge/Scripts/python.exe -m forge.web.app` boots; `POST /forge` works.
2. `ANTHROPIC_API_KEY` in `.env` (the auto-fill agent uses Claude). For the live test only.
3. You may add `pypdf` to `requirements.txt` (and install into `.venv_forge`).

## 9. Definition of done
`POST /forge/sheet` accepts a `.docx`/`.pdf` upload, extracts the text, runs it through the existing
auto-fill agent, and returns the same `{character, warnings}` as `/forge`; the "no readable text" case
returns a clean warning; tests green; the front-end request/response contract is documented for the build
chat. The structured-template path remains a separate future chat.

---

## 10. HAND-BACK — built ✅ (front-end contract for the build chat)

**Status: back-end complete.** Delivered:
- `forge/agents/sheet_extract.py` — `extract_sheet_text(filename, data: bytes) -> str`
  (`.docx` via python-docx incl. table cells, `.pdf` via pypdf, `.txt`/`.md` pass-through;
  raises `UnsupportedSheetType`; scanned/image PDFs extract to `""`).
- `POST /forge/sheet` in `forge/web/app.py` (multipart) — mirrors `/forge`'s try/except +
  `log_forge` + CORS.
- `pypdf>=4` added to `requirements.txt` (installed into `.venv_forge`).
- Tests: `tests/test_sheet_extract.py` (extraction + assembly, no API key). Existing
  `test_autofill*.py` still green.

### Endpoint contract
`POST /forge/sheet` — `Content-Type: multipart/form-data`

| field      | required | default        | notes                                    |
|------------|----------|----------------|------------------------------------------|
| `file`     | **yes**  | —              | the `.docx`/`.pdf`/`.txt`/`.md` upload    |
| `ruleset`  | no       | `dnd5e-2014`   | same slugs as `/forge`                    |
| `kind`     | no       | `character`    | a sheet is almost always a PC             |
| `rulesMode`| no       | `relaxed`      | `strict` \| `relaxed` (PC only)           |

**Success `200`** — identical to `/forge`:
`{ "character": {…}, "warnings": [{ "level": "...", "message": "..." }] }`

**Errors** (all clean JSON, never a 500 page):
- `400 {error:"no_file"}` — no file attached
- `400 {error:"unsupported_type", message}` — extension not one of `.docx/.pdf/.txt/.md`
- `422 {error:"no_text", message}` — file read but no text layer (scanned image PDF)
- `422 {error:"extract_failed", message}` — corrupt/unreadable file
- `502 {error:"forge_failed", message}` — provider/agent error

### Front-end wiring (do in the build chat — NOT done here)
Add an `<input type="file">`; on change, POST `FormData` to `/forge/sheet`, then land
`res.character` into the draft and switch to the Studio — exactly as `forgeViaBridge()`
does with `/forge` today. Sketch:

```js
async function forgeFromSheet(file, { ruleset, kind = 'character', rulesMode = 'relaxed' } = {}) {
  const fd = new FormData();
  fd.append('file', file);
  if (ruleset)  fd.append('ruleset', ruleset);
  fd.append('kind', kind);
  fd.append('rulesMode', rulesMode);
  const res = await fetch(`${BRIDGE}/forge/sheet`, { method: 'POST', body: fd }); // no Content-Type header — let the browser set the multipart boundary
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || 'Upload failed');
  landDraftIntoStudio(data.character, data.warnings); // same landing path as /forge
}
```

> **Live test (manual, behind the key):** with `ANTHROPIC_API_KEY` set, POST a real PC
> `.docx`/`.pdf` to `/forge/sheet` → a sensible draft. The fake-model tests already cover
> assembly + the contract shape without a key.
