/**
 * API layer — all fetch/SSE calls to the FastAPI backend.
 * No DOM manipulation here; return data or call callbacks.
 */

const BASE = "";

export async function probeFile(path) {
  const res = await fetch(`${BASE}/api/probe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  return res.json();
}

export async function browseVideo() {
  const res = await fetch(`${BASE}/api/browse`);
  return res.json();
}

export async function browseAudio() {
  const res = await fetch(`${BASE}/api/browse-audio`);
  return res.json();
}

export async function browseFolder() {
  const res = await fetch(`${BASE}/api/browse-folder`);
  return res.json();
}

export async function openFolder(folder) {
  await fetch(`${BASE}/api/open-folder`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder }),
  });
}

/**
 * Generic SSE runner.
 * @param {string} endpoint  - e.g. '/api/video/pipeline'
 * @param {object} body      - JSON payload
 * @param {function} onEvent - called with each parsed SSE object
 * @returns {Promise<void>}  - resolves when stream ends
 */
export function runSSE(endpoint, body, onEvent) {
  return new Promise((resolve, reject) => {
    fetch(`${BASE}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
      .then((res) => {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        function pump() {
          reader.read().then(({ done, value }) => {
            if (done) { resolve(); return; }
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split("\n\n");
            buffer = parts.pop();
            for (const part of parts) {
              const line = part.trim();
              if (line.startsWith("data: ")) {
                try {
                  onEvent(JSON.parse(line.slice(6)));
                } catch {}
              }
            }
            pump();
          });
        }
        pump();
      })
      .catch(reject);
  });
}

// ── Convenience wrappers ─────────────────────────────────────────

export const processVideo  = (body, cb) => runSSE("/api/video/pipeline", body, cb);
export const processAudio  = (body, cb) => runSSE("/api/audio/loop",     body, cb);
export const mergeFiles    = (body, cb) => runSSE("/api/merge",           body, cb);
export const cropVideo     = (body, cb) => runSSE("/api/video/crop",      body, cb);
export const upscaleVideo  = (body, cb) => runSSE("/api/video/upscale",   body, cb);
export const loopVideoOnly = (body, cb) => runSSE("/api/video/loop",      body, cb);
export const makeThumbnail = (body, cb) => runSSE("/api/thumbnail",       body, cb);
