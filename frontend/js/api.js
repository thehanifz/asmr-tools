// ═══════════════════════════════════════════════
//  API — all fetch calls to FastAPI backend
// ═══════════════════════════════════════════════

const BASE = "";

export async function browseVideo() {
  const res = await fetch(`${BASE}/api/browse`);
  const data = await res.json();
  return data.path || "";
}

export async function browseAudio() {
  const res = await fetch(`${BASE}/api/browse-audio`);
  const data = await res.json();
  return data.path || "";
}

export async function probeFile(path) {
  const res = await fetch(`${BASE}/api/probe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  return await res.json();
}

export async function processVideo(payload) {
  return fetch(`${BASE}/api/video/pipeline`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function processAudio(payload) {
  return fetch(`${BASE}/api/audio/loop`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function processDenoiseSSE(payload) {
  return fetch(`${BASE}/api/denoise`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function processMerge(payload) {
  return fetch(`${BASE}/api/merge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function extractThumbnail(payload) {
  const res = await fetch(`${BASE}/api/thumbnail`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return await res.json();
}

export function thumbnailPreviewUrl(path) {
  return `${BASE}/api/thumbnail/preview?path=${encodeURIComponent(path)}`;
}
