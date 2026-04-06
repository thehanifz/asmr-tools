/**
 * UI helpers — per-panel toast, log, progress, status.
 * All functions accept a panelId so each panel is independent.
 */

// ── Toast ──────────────────────────────────────────────────────────
export function toast(msg, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ── Per-panel log ──────────────────────────────────────────────────
export function log(panelId, msg, type = "") {
  const box = document.getElementById(`${panelId}-log`);
  if (!box) return;
  box.style.display = "block";
  const line = document.createElement("span");
  line.className = `log-line${type ? ` log-${type}` : ""}`;
  line.textContent = msg + "\n";
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}

export function clearLog(panelId) {
  const box = document.getElementById(`${panelId}-log`);
  if (box) { box.innerHTML = ""; box.style.display = "none"; }
}

// ── Per-panel progress ─────────────────────────────────────────────
export function setProgress(panelId, pct) {
  const wrap = document.getElementById(`${panelId}-progress`);
  const fill = document.getElementById(`${panelId}-progress-fill`);
  if (!wrap || !fill) return;
  wrap.style.display = "block";
  fill.classList.remove("indeterminate");
  fill.style.width = `${pct}%`;
}

export function setProgressIndeterminate(panelId) {
  const wrap = document.getElementById(`${panelId}-progress`);
  const fill = document.getElementById(`${panelId}-progress-fill`);
  if (!wrap || !fill) return;
  wrap.style.display = "block";
  fill.classList.add("indeterminate");
  fill.style.width = "40%";
}

export function hideProgress(panelId) {
  const wrap = document.getElementById(`${panelId}-progress`);
  if (wrap) wrap.style.display = "none";
}

// ── Panel status badge ────────────────────────────────────────────
export function setPanelStatus(panelId, msg) {
  const el = document.getElementById(`${panelId === "video" ? "video" : panelId === "audio" ? "audio" : "merge"}-status`);
  if (el) el.textContent = msg;
}

export function setPanelReady(panelId, filename) {
  setPanelStatus(panelId, `✅ ${filename}`);
}

export function setPanelProcessing(panelId) {
  setPanelStatus(panelId, "⏳ Processing...");
}

export function setPanelIdle(panelId) {
  setPanelStatus(panelId, "—");
}

// ── Probe card helpers ────────────────────────────────────────────
export function showProbe(panelId) {
  const el = document.getElementById(`${panelId}-probe`);
  if (el) el.style.display = "flex";
}

export function hideProbe(panelId) {
  const el = document.getElementById(`${panelId}-probe`);
  if (el) el.style.display = "none";
}
