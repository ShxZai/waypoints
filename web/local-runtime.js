// Local runtime for Waypoints.
// The page was first written as a Claude Artifact against `window.claude.use(name)`.
// This file provides that same small interface, backed by the local Python
// server instead of the artifact platform:
//   db        -> /api/docs    (SQLite)
//   sample    -> /api/ask     (the teacher: your Claude subscription or an API key)
//   downloads -> a normal browser download
// plus window.waypointsLocal for things the artifact never had (real Python,
// status, notes files).
(function () {
  "use strict";
  const HEADERS = { "Content-Type": "application/json", "X-Waypoints": "1" };

  const db = {
    collection(name) {
      return {
        async get() {
          const r = await fetch("/api/docs/" + encodeURIComponent(name));
          if (!r.ok) throw new Error("Couldn't load " + name);
          const j = await r.json();
          return { docs: j.docs.map(d => ({ id: d.id, data: () => d.data })) };
        },
        doc(id) {
          return {
            async set(data) {
              const r = await fetch("/api/docs/" + encodeURIComponent(name) + "/" + encodeURIComponent(id),
                { method: "PUT", headers: HEADERS, body: JSON.stringify(data) });
              if (!r.ok) throw new Error("Couldn't save " + name + "/" + id);
            }
          };
        }
      };
    }
  };

  // One teacher request. Resolves with the server's final {result, text, usage};
  // rejects with {code, message, text?} like the artifact's sample() did.
  async function call(input, opts, json) {
    opts = opts || {};
    let res;
    try {
      res = await fetch("/api/ask", {
        method: "POST", headers: HEADERS, signal: opts.signal,
        body: JSON.stringify({ input, json, schema: opts.schema || null, tier: opts.modelTier || "default", web: !!opts.web })
      });
    } catch (e) {
      if (opts.signal && opts.signal.aborted) throw { code: "cancelled", message: "Stopped." };
      throw { code: "upstream_error", message: "The Waypoints server isn't reachable. Is run.bat still open?" };
    }
    if (!res.ok || !res.body) throw { code: "upstream_error", message: "The server answered with error " + res.status + "." };
    const reader = res.body.getReader(), dec = new TextDecoder();
    let buf = "", text = "", done = null;
    try {
      for (;;) {
        const { value, done: end } = await reader.read();
        if (end) break;
        buf += dec.decode(value, { stream: true });
        let nl;
        while ((nl = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, nl);
          buf = buf.slice(nl + 1);
          if (!line.trim()) continue;
          const ev = JSON.parse(line);
          if (ev.t === "delta") {
            text += ev.d;
            if (opts.onText) { try { opts.onText({ text, delta: ev.d }); } catch (e) { console.error(e); } }
          } else if (ev.t === "error") {
            throw { code: ev.code, message: ev.message, text: ev.text || text || undefined };
          } else if (ev.t === "done") {
            done = ev;
          }
        }
      }
    } catch (e) {
      if (opts.signal && opts.signal.aborted) throw { code: "cancelled", message: "Stopped.", text: text || undefined };
      if (e && e.code) throw e;
      throw { code: "upstream_error", message: String((e && e.message) || e), text: text || undefined };
    }
    if (!done) throw { code: "upstream_error", message: "The answer was cut off.", text: text || undefined };
    window.dispatchEvent(new CustomEvent("wp-teacher-done", { detail: done.usage || {} }));
    return done;
  }
  const sample = async (input, opts) => {
    const d = await call(input, opts, false);
    return { text: String(d.result), truncated: false, modelTierApplied: (opts && opts.modelTier) || "default" };
  };
  sample.json = async (input, opts) => (await call(input, opts, true)).result;

  const downloads = {
    async save({ filename, data }) {
      const blob = data instanceof Blob ? data : new Blob([data], { type: "text/markdown;charset=utf-8" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      return { status: "saved" };
    }
  };

  let statusPromise = null;
  function status(refresh) {
    if (refresh || !statusPromise) {
      statusPromise = fetch("/api/status").then(r => r.json())
        .catch(() => ({ ready: false, message: "The Waypoints server isn't reachable. Start it with run.bat." }));
    }
    return statusPromise;
  }

  window.waypointsLocal = {
    status,
    async limits() {
      try { return (await (await fetch("/api/limits")).json()).limits; } catch (e) { return null; }
    },
    async run(code) {
      const r = await fetch("/api/run", { method: "POST", headers: HEADERS, body: JSON.stringify({ code }) });
      if (!r.ok) throw new Error("Couldn't run the code (server error " + r.status + ").");
      return r.json();
    },
    async saveNote(name, markdown) {
      await fetch("/api/notes/" + encodeURIComponent(name), { method: "POST", headers: HEADERS, body: JSON.stringify({ markdown }) });
    }
  };

  window.claude = {
    async use(name) {
      if (name === "db") return db;
      if (name === "downloads") return downloads;
      if (name === "sample") { const s = await status(); return s.ready ? sample : null; }
      return null;
    }
  };
})();
