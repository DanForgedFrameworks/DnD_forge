/* forge-bridge.js — thin adapter between the Forge front-end and the local Flask bridge.
 *
 * Live-first, fallback-second: every call tries the bridge; on any failure it falls back to
 * bundled sample data + the page's own computePrompt(), so the file still demos in the design
 * preview and lights up with live data + real portraits the moment it's opened against a running
 * Flask server.
 *
 * Usage:
 *   const forge = new ForgeBridge({
 *     baseUrl: 'http://localhost:5000',     // optional; persisted in localStorage
 *     computePrompt: window.computePrompt,   // the page's canonical client-side prompt builder
 *     fallback: window.FORGE_FALLBACK,       // bundled sample data (fallback-data.js)
 *   });
 *   if (await forge.isLive()) { ... }        // optional banner: "live" vs "preview (offline)"
 *
 * NOTE: an HTTPS page cannot reach http://localhost (mixed content) — Pages copies stay offline.
 * Live mode needs the HTML opened locally (file://) or served by Flask (same origin).
 */
(function (global) {
  const DEFAULT_BASE = "http://localhost:5000";

  class ForgeBridge {
    constructor(opts = {}) {
      const stored = global.localStorage && localStorage.getItem("forgeBaseUrl");
      this.baseUrl = (opts.baseUrl || stored || DEFAULT_BASE).replace(/\/+$/, "");
      this.computePrompt = opts.computePrompt || null;
      this.fallback = opts.fallback || global.FORGE_FALLBACK || {};
      this.timeoutMs = opts.timeoutMs || 4000;
      this._live = null;
    }

    setBaseUrl(url) {
      this.baseUrl = String(url).replace(/\/+$/, "");
      if (global.localStorage) localStorage.setItem("forgeBaseUrl", this.baseUrl);
      this._live = null;
    }

    async _json(path, init) {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), this.timeoutMs);
      try {
        const r = await fetch(this.baseUrl + path, { ...init, signal: ctrl.signal });
        if (!r.ok) throw new Error("HTTP " + r.status + ": " + (await r.text()).slice(0, 300));
        return await r.json();
      } finally {
        clearTimeout(timer);
      }
    }

    /** True if the bridge answered. Cached; cleared by setBaseUrl(). */
    async isLive() {
      if (this._live !== null) return this._live;
      try { await this._json("/rulesets"); this._live = true; }
      catch { this._live = false; }
      return this._live;
    }

    _rs() { return this.fallback.rulesets || {}; }
    _chars() { return this.fallback.characters || []; }

    // --- rulesets ----------------------------------------------------------
    async rulesets() {
      try { return (await this._json("/rulesets")).rulesets; }
      catch {
        return Object.values(this._rs()).map((r) => ({ slug: r.slug, label: r.label, extends: r.extends || null }));
      }
    }
    async ruleset(slug) {
      try { return await this._json("/ruleset/" + encodeURIComponent(slug)); }
      catch { return this._rs()[slug] || this._rs()[this.fallback.defaultRuleset] || null; }
    }

    // --- forge (brain-dump -> character) -----------------------------------
    async forge(dump, { ruleset, kind } = {}) {
      try {
        return await this._json("/forge", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ dump, ruleset, kind }),
        });
      } catch {
        return {
          character: this._chars()[0] || null,
          warnings: [{ level: "info", message: "Bridge offline — showing a bundled sample (no live generation)." }],
          offline: true,
        };
      }
    }

    // --- art ---------------------------------------------------------------
    async artPreview(character, state) {
      try {
        return (await this._json("/art/preview", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ character, state }),
        })).prompt;
      } catch {
        return this.computePrompt ? this.computePrompt(character, state) : "";
      }
    }
    async art(idOrCharacter, state, { tweak, seed } = {}) {
      const body = typeof idOrCharacter === "string"
        ? { id: idOrCharacter, state, tweak, seed }
        : { character: idOrCharacter, state, tweak, seed };
      try {
        return await this._json("/art", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } catch {
        const ch = typeof idOrCharacter === "string" ? {} : idOrCharacter;
        return {
          offline: true, imageUrl: null, seed: seed ?? null,
          prompt: this.computePrompt ? this.computePrompt(ch, state) : "",
          message: "Bridge offline — use the manual drop-slot.",
        };
      }
    }

    // --- characters --------------------------------------------------------
    async characters() {
      try { return (await this._json("/character")).characters; }
      catch {
        return this._chars().map((c) => ({ id: c.id, name: c.name, kind: c.kind, ruleset: c.ruleset, level: (c.pc || {}).level }));
      }
    }
    async character(id) {
      try { return await this._json("/character/" + encodeURIComponent(id)); }
      catch { return this._chars().find((c) => c.id === id) || null; }
    }
    async saveCharacter(character) {
      try {
        return await this._json("/character", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ character }),
        });
      } catch {
        return { id: character.id, character, offline: true };
      }
    }
  }

  global.ForgeBridge = ForgeBridge;
})(typeof window !== "undefined" ? window : this);
