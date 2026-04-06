/**
 * UI helpers — DOM utilities, toast, progress, log box.
 * No business logic here.
 */

/** Show a toast notification */
export function toast(msg, type = "info") {
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

/** Set progress bar (0-100) */
export function setProgress(pct) {
  const bar = document.getElementById("progress-bar");
  if (bar) bar.style.width = `${pct}%`;
}

/** Append a line to the log box */
export function log(msg, type = "") {
  const box = document.getElementById("log-box");
  if (!box) return;
  const line = document.createElement("div");
  line.className = `log-line ${type}`;
  line.textContent = msg;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}

/** Clear log box */
export function clearLog() {
  const box = document.getElementById("log-box");
  if (box) box.innerHTML = "";
}

/** Set status text */
export function setStatus(msg) {
  const el = document.getElementById("progress-info");
  if (el) el.textContent = msg;
}

/** Toggle element visibility */
export function show(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove("hidden");
}
export function hide(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add("hidden");
}

/** Mark a panel as ready (green indicator) */
export function setPanelReady(panelId, filename) {
  const indicator = document.querySelector(`#${panelId} .panel-status`);
  if (!indicator) return;
  indicator.className = "panel-status ready";
  indicator.textContent = `✅ ${filename}`;
}

/** Mark a panel as processing */
export function setPanelProcessing(panelId) {
  const indicator = document.querySelector(`#${panelId} .panel-status`);
  if (!indicator) return;
  indicator.className = "panel-status processing";
  indicator.textContent = "⏳ Processing...";
}

/** Mark a panel as idle */
export function setPanelIdle(panelId) {
  const indicator = document.querySelector(`#${panelId} .panel-status`);
  if (!indicator) return;
  indicator.className = "panel-status";
  indicator.textContent = "";
}
