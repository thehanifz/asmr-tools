// ═══════════════════════════════════════════════
//  API — all fetch calls to FastAPI backend
// ═══════════════════════════════════════════════

const BASE = "";

// ── Server file picker ──────────────────────────
// The backend runs headless (no desktop), so the old tkinter file
// dialogs can never open. Every panel instead picks from files that
// already live on the server (media/ + sound library), or uploads a
// new one from the browser. Same contract as before: resolves with
// a path string ("" = cancelled) or, for multi, an array of paths.
function _fmtDur(s) {
  s = Math.round(s || 0);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function _ensurePickerDom() {
  let overlay = document.getElementById("serverPickerOverlay");
  if (overlay) return overlay;
  overlay = document.createElement("div");
  overlay.id = "serverPickerOverlay";
  overlay.style.cssText =
    "position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:9999;" +
    "display:none;align-items:center;justify-content:center;";
  overlay.innerHTML = `
    <div style="background:var(--panel,#1b1e26);color:var(--text,#e8eaf0);
      width:min(580px,94vw);max-height:82vh;overflow-y:auto;border-radius:12px;
      padding:18px;border:1px solid var(--border,#333a45);
      box-shadow:0 18px 50px rgba(0,0,0,.5);font-size:13px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <strong id="spTitle" style="font-size:14px;">Pilih Berkas dari Server</strong>
        <button id="spClose" type="button" style="background:none;border:none;color:inherit;
          font-size:18px;cursor:pointer;line-height:1;">✕</button>
      </div>
      <button id="spUploadBtn" type="button" style="width:100%;padding:9px;margin-bottom:12px;
        border-radius:8px;border:1px dashed var(--border,#333a45);background:none;color:inherit;cursor:pointer;">
        ⬆ Upload berkas baru dari perangkat ini…
      </button>
      <input type="file" id="spFileInput" style="display:none;">
      <div id="spList"><div style="color:var(--text-muted,#8a90a0);padding:8px 0;">Memuat daftar berkas…</div></div>
      <div id="spFooter" style="display:none;gap:8px;margin-top:12px;">
        <button id="spCancel" type="button" style="flex:1;padding:9px;border-radius:8px;cursor:pointer;
          border:1px solid var(--border,#333a45);background:none;color:inherit;">Batal</button>
        <button id="spConfirm" type="button" style="flex:2;padding:9px;border-radius:8px;cursor:pointer;
          border:none;background:var(--accent,#f97316);color:#fff;font-weight:600;">Pilih</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  return overlay;
}

function pickServerFiles(kind, multi = false) {
  return new Promise((resolve) => {
    const overlay = _ensurePickerDom();
    const listEl = overlay.querySelector("#spList");
    const footer = overlay.querySelector("#spFooter");
    const fileInput = overlay.querySelector("#spFileInput");
    const selected = new Set();
    let done = false;

    overlay.querySelector("#spTitle").textContent =
      kind === "video" ? "🎬 Pilih Video dari Server" : "🎧 Pilih Audio dari Server";
    footer.style.display = multi ? "flex" : "none";
    fileInput.accept = kind === "video" ? "video/*,.mkv" : "audio/*";
    overlay.style.display = "flex";

    const finish = (val) => {
      if (done) return;
      done = true;
      overlay.style.display = "none";
      resolve(val);
    };

    async function load(preselectName = "") {
      listEl.innerHTML = '<div style="color:var(--text-muted,#8a90a0);padding:8px 0;">Memuat daftar berkas…</div>';
      let data;
      try {
        const res = await fetch(`${BASE}/api/library/files?kind=${kind}`);
        data = await res.json();
      } catch (e) {
        listEl.innerHTML = `<div style="color:#f66;padding:8px 0;">Gagal memuat daftar: ${e.message}</div>`;
        return;
      }
      const groups = data.groups || [];
      if (!groups.length) {
        listEl.innerHTML = '<div style="color:var(--text-muted,#8a90a0);padding:10px 0;">Belum ada berkas di server. Upload dulu lewat tombol di atas.</div>';
        return;
      }
      listEl.innerHTML = "";
      groups.forEach((g) => {
        const h = document.createElement("div");
        h.style.cssText = "font-weight:700;margin:10px 0 4px;color:var(--text-muted,#8a90a0);font-size:11px;text-transform:uppercase;letter-spacing:.04em;";
        h.textContent = g.label;
        listEl.appendChild(h);
        g.items.forEach((item) => {
          const row = document.createElement("div");
          row.style.cssText = "display:flex;justify-content:space-between;gap:10px;padding:8px 10px;border:1px solid var(--border,#333a45);border-radius:8px;margin-bottom:6px;cursor:pointer;align-items:center;";
          const meta = [item.duration ? _fmtDur(item.duration) : null,
                        item.size_mb ? `${item.size_mb} MB` : null].filter(Boolean).join(" · ");
          row.innerHTML = `<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${multi ? "☐ " : ""}${item.name}</span><span style="color:var(--text-muted,#8a90a0);white-space:nowrap;">${meta}</span>`;
          const mark = () => {
            const on = selected.has(item.path);
            row.style.borderColor = on ? "var(--accent,#f97316)" : "var(--border,#333a45)";
            row.querySelector("span").textContent = (multi ? (on ? "☑ " : "☐ ") : "") + item.name;
            overlay.querySelector("#spConfirm").textContent = `Pilih (${selected.size})`;
          };
          row.addEventListener("click", () => {
            if (!multi) return finish([item.path]);
            selected.has(item.path) ? selected.delete(item.path) : selected.add(item.path);
            mark();
          });
          listEl.appendChild(row);
          if (preselectName && item.name === preselectName) {
            if (!multi) return finish([item.path]);
            selected.add(item.path);
            mark();
          }
        });
      });
    }

    overlay.querySelector("#spClose").onclick = () => finish([]);
    overlay.querySelector("#spCancel").onclick = () => finish([]);
    overlay.querySelector("#spConfirm").onclick = () => finish([...selected]);
    overlay.onmousedown = (e) => { if (e.target === overlay) finish([]); };
    overlay.querySelector("#spUploadBtn").onclick = () => fileInput.click();
    fileInput.onchange = async () => {
      const file = fileInput.files[0];
      fileInput.value = "";
      if (!file) return;
      listEl.innerHTML = '<div style="padding:8px 0;">Mengupload berkas ke server…</div>';
      try {
        const fd = new FormData();
        fd.append("file", file);
        const res = await fetch(`${BASE}/api/live/library/${kind}/add`, { method: "POST", body: fd });
        const data = await res.json();
        if (data.status !== "success") throw new Error(data.error || "Upload gagal");
        await load(data.filename);
        if (multi) listEl.insertAdjacentHTML("afterbegin", '<div style="color:#4ade80;padding:4px 0;">✓ Upload selesai — berkas baru sudah ditandai.</div>');
      } catch (e) {
        listEl.innerHTML = `<div style="color:#f66;padding:8px 0;">Upload gagal: ${e.message}</div>`;
      }
    };

    load();
  });
}

export async function browseVideo() {
  const paths = await pickServerFiles("video", false);
  return paths[0] || "";
}

export async function browseAudio() {
  const paths = await pickServerFiles("audio", false);
  return paths[0] || "";
}

export async function fetchServerFiles(kind) {
  const res = await fetch(`${BASE}/api/library/files?kind=${kind}`);
  if (!res.ok) throw new Error("Daftar berkas server tidak tersedia");
  return await res.json();
}

// Upload-only: langsung buka file chooser perangkat, upload ke server,
// resolve dengan path server-nya ("" = batal). Tanpa modal daftar berkas —
// daftar berkasnya sudah ada di dropdown Pustaka Suara (panel Sound Layer).
export function uploadAudioFromDevice() {
  return new Promise((resolve, reject) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "audio/*";
    input.style.display = "none";
    document.body.appendChild(input);
    let done = false;
    const finish = (fn, val) => {
      if (done) return;
      done = true;
      input.remove();
      fn(val);
    };
    input.addEventListener("cancel", () => finish(resolve, ""));
    input.addEventListener("change", async () => {
      const file = input.files[0];
      if (!file) return finish(resolve, "");
      try {
        const fd = new FormData();
        fd.append("file", file);
        const res = await fetch(`${BASE}/api/live/library/audio/add`, { method: "POST", body: fd });
        const data = await res.json();
        if (data.status !== "success") throw new Error(data.error || "Upload gagal");
        const catalog = await fetchServerFiles("audio");
        const hit = (catalog.groups || []).flatMap((g) => g.items).find((it) => it.name === data.filename);
        if (!hit) throw new Error("Berkas terupload tapi tidak ditemukan di server");
        finish(resolve, hit.path);
      } catch (e) {
        finish(reject, e);
      }
    });
    input.click();
  });
}

export async function fetchLibrarySounds() {
  const res = await fetch(`${BASE}/api/library/sounds`);
  if (!res.ok) throw new Error("Pustaka suara tidak tersedia");
  return await res.json();
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

// ── Sound Layer API ──────────────────────────────
export async function browseFolderAudio() {
  const res = await fetch(`${BASE}/api/sound-layer/browse-folder-audio`);
  const data = await res.json();
  return data;
}

export async function previewSoundLayer(payload) {
  const res = await fetch(`${BASE}/api/sound-layer/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return await res.json();
}

// ── Clip Concatenator (Concat) API ─────────────────
export async function browseVideos() {
  return pickServerFiles("video", true);
}

export async function probeVideos(paths) {
  const res = await fetch(`${BASE}/api/concat/probe-videos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paths }),
  });
  return await res.json();
}

export async function processLoopBA(payload) {
  return fetch(`${BASE}/api/loop-ba/render`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

