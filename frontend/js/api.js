/**
 * API client — all fetch + SSE calls to FastAPI backend.
 */
const BASE = "";

// ── Generic SSE runner ─────────────────────────────────────────────
export function runSSE(url, body, onEvent) {
  return new Promise((resolve, reject) => {
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        function pump() {
          reader.read().then(({ done, value }) => {
            if (done) { resolve(); return; }
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();
            for (const line of lines) {
              if (line.startsWith("data: ")) {
                try { onEvent(JSON.parse(line.slice(6))); } catch {}
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

// ── Probe ──────────────────────────────────────────────────────────
export async function probeFile(filePath) {
  const res = await fetch(`${BASE}/api/probe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: filePath }),
  });
  return res.json();
}

// ── Browse dialogs ─────────────────────────────────────────────────
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

// ── Video pipeline ─────────────────────────────────────────────────
export function processVideo(payload, onEvent) {
  return runSSE(`${BASE}/api/video/pipeline`, payload, onEvent);
}

// ── Audio loop ────────────────────────────────────────────────────
export function processAudio(payload, onEvent) {
  return runSSE(`${BASE}/api/audio/loop`, payload, onEvent);
}

// ── Merge ─────────────────────────────────────────────────────────
export function mergeFiles(payload, onEvent) {
  return runSSE(`${BASE}/api/merge`, payload, onEvent);
}

// ── Thumbnail ─────────────────────────────────────────────────────
export async function makeThumbnail(payload) {
  const res = await fetch(`${BASE}/api/thumbnail`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

// ── Open folder ───────────────────────────────────────────────────
export async function openFolder(folderPath) {
  await fetch(`${BASE}/api/open-folder`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: folderPath }),
  });
}
