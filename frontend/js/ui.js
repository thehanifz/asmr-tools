// ═══════════════════════════════════════════════
//  UI helpers — toast, log, progress, file-info
// ═══════════════════════════════════════════════

// ── Toast ────────────────────────────────────────
export function toast(msg, type = "info", duration = 3500) {
  const container = document.getElementById("toastContainer");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), duration);
}

// ── Log box ──────────────────────────────────────
export function logAppend(logId, text, cls = "") {
  const box = document.getElementById(logId);
  if (!box) return;
  box.classList.add("visible");
  const line = document.createElement("div");
  line.className = "log-line" + (cls ? " " + cls : "");
  line.textContent = text;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}

export function logClear(logId) {
  const box = document.getElementById(logId);
  if (box) { box.innerHTML = ""; box.classList.remove("visible"); }
}

// ── Progress ─────────────────────────────────────
export function progressShow(wrapId, fillId, labelId, label = "", indeterminate = true) {
  const wrap = document.getElementById(wrapId);
  const fill = document.getElementById(fillId);
  const lbl  = document.getElementById(labelId);
  if (wrap) wrap.classList.add("visible");
  if (fill) {
    if (indeterminate) fill.classList.add("indeterminate");
    else { fill.classList.remove("indeterminate"); fill.style.width = "0%"; }
  }
  if (lbl) lbl.textContent = label;
}

export function progressDone(wrapId, fillId, labelId, label = "Selesai") {
  const fill = document.getElementById(fillId);
  const lbl  = document.getElementById(labelId);
  if (fill) { fill.classList.remove("indeterminate"); fill.style.width = "100%"; }
  if (lbl) lbl.textContent = label;
}

export function progressHide(wrapId) {
  const wrap = document.getElementById(wrapId);
  if (wrap) wrap.classList.remove("visible");
}

// ── File info badge ──────────────────────────────
export function showFileInfo(infoId, info) {
  const el = document.getElementById(infoId);
  if (!el) return;
  const parts = [];
  if (info.filename)     parts.push(info.filename);
  if (info.duration_str) parts.push(`⏱ ${info.duration_str}`);
  if (info.resolution)   parts.push(`🖥 ${info.resolution}`);
  if (info.fps)          parts.push(`${info.fps}fps`);
  if (info.size_str)     parts.push(`💾 ${info.size_str}`);
  if (info.bitrate_str)  parts.push(info.bitrate_str);
  if (info.audio_codec)  parts.push(`🎵 ${info.audio_codec}`);
  if (info.sample_rate)  parts.push(`${info.sample_rate}Hz`);

  el.innerHTML = parts.map(p =>
    `<span>${p}</span>`
  ).join(" · ");
  el.classList.add("visible");
}

// ── SSE stream consumer ──────────────────────────
/**
 * Consume an SSE endpoint and pipe logs to a log box.
 * Returns a Promise<{ok, finalData}>.
 */
export function consumeSSE(url, payload, logId, progressWrapId, progressFillId, progressLabelId) {
  return new Promise((resolve) => {
    logClear(logId);
    progressShow(progressWrapId, progressFillId, progressLabelId, "Memproses...");

    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(res => {
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finalData = null;

      function read() {
        reader.read().then(({ done, value }) => {
          if (done) {
            progressDone(progressWrapId, progressFillId, progressLabelId);
            resolve({ ok: true, finalData });
            return;
          }
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop();
          for (const part of parts) {
            if (!part.startsWith("data: ")) continue;
            try {
              const data = JSON.parse(part.slice(6));
              if (data.log) {
                logAppend(logId, data.log);
              } else if (data.status === "done" || data.status === "all_done") {
                finalData = data;
                logAppend(logId, `✓ ${data.output || "Selesai"} ${data.final_size || data.output_size || ""}`, "done");
              } else if (data.status === "error") {
                logAppend(logId, `✗ Error (code ${data.code})`, "error");
                progressDone(progressWrapId, progressFillId, progressLabelId, "Error");
                resolve({ ok: false, finalData: null });
              } else if (data.type === "step_start") {
                logAppend(logId, `▶ ${data.label}`, "step");
              } else if (data.type === "step_done") {
                logAppend(logId, `✓ ${data.label} — ${data.elapsed} · ${data.output_size}`, "done");
              } else if (data.type === "done") {
                finalData = data;
                logAppend(logId, `✓ ${data.output} · ${data.size} · ${data.elapsed}`, "done");
              }
            } catch {}
          }
          read();
        });
      }
      read();
    }).catch(err => {
      logAppend(logId, `✗ ${err.message}`, "error");
      resolve({ ok: false, finalData: null });
    });
  });
}
