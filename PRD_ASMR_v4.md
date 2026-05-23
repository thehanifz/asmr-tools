# PRD: ASMR Tools — Improvement Batch v4
**Dokumen:** Product Requirements Document  
**Versi:** 4.0  
**Tanggal:** 23 Mei 2026  
**Repo:** https://github.com/thehanifz/asmr-tools  
**Status:** Final — Siap Implementasi  
**Predecessor:** PRD v3 (Sound Layering & Smart Merge)

---

## 1. Overview & Executive Summary

Batch v4 berfokus pada **dua tema besar**:

1. **Kenyamanan UI** — Collapse/toggle pada section yang jarang diubah di tab Video dan Sound Layer agar scroll lebih pendek dan UI terasa ringan.
2. **Performa & Stabilitas** — Auto-detect GPU untuk Video pipeline, perbaikan thread management (n-1), dan Auto Cleanup file temporary yang menumpuk di disk.

Satu keputusan desain penting: **tab Merge mempertahankan manual audio layers**, namun default source diubah ke **Sound Layer Output** agar alur kerja normal lebih cepat tanpa membuang fleksibilitas.

Total ada **7 item perubahan** — 2 backend, 4 frontend/UI, 1 endpoint baru.

---

## 2. Problem Statement

| # | Masalah | File Sumber | Dampak |
|---|---------|-------------|--------|
| P1 | `get_thread_flags()` memakai semua core (maks hardcoded 8) tanpa menyisakan untuk OS | `core/env.py` | PC bisa freeze di mesin 4-core saat render |
| P2 | Tab Video punya 3 section besar (Crop, Fade, XFade) selalu terbuka | `frontend/index.html` | Harus scroll jauh untuk sampai tombol Proses |
| P3 | Tab Merge default ke "Manual Layers" bukan Sound Layer Output | `panel-merge.js` | Alur kerja normal butuh extra klik setiap sesi |
| P4 | Optional Sound Pool section selalu terlihat meski tidak dipakai | `frontend/index.html` | Tab Sound Layer terasa padat |
| P5 | Optional Sound Pool hanya bisa browse seluruh folder | `panel-sound-layer.js` | Tidak bisa pilih file individual tanpa folder khusus |
| P6 | File sementara (`_tmp_*`, `._layered`, `._preview_`) terus menumpuk | Semua pipeline | Disk habis setelah banyak sesi render |
| P7 | Video pipeline hardcode `libx264` meski GPU-capable sudah ada di `core/env.py` | `api/video.py` | Tidak memanfaatkan GPU NVIDIA yang ada; render lama |

---

## 3. Goals & Success Metrics

| Goal | Metric Sukses |
|------|---------------|
| CPU tidak pernah 100% karena FFmpeg | `filter_threads = max(1, cpu_count - 1)` di semua render |
| Tab Video lebih ringkas | Tombol Proses Video terlihat tanpa scroll di viewport 768px |
| Merge default ke Sound Layer | Setelah render Sound Layer, tab Merge langsung siap tanpa klik tambahan |
| GPU dimanfaatkan bila tersedia | `h264_nvenc` otomatis aktif jika terdeteksi; fallback `libx264` jika tidak |
| Disk terkontrol | 1 klik bersihkan semua `_tmp_` dan `._preview_` di workspace aktif |

---

## 4. Target Users & Personas

**Persona: Solo ASMR Creator (Windows, GPU NVIDIA)**
- Setup: PC Windows, GPU NVIDIA mid-range (GTX 1060+), 8–16 core
- Workflow: Video + Audio pipeline dalam satu sesi 30–60 menit
- Pain point: PC sering freeze saat render panjang; harus scroll banyak di UI; disk penuh

---

## 5. Scope

### ✅ In-Scope (v4)

| # | Item | Kompleksitas | File Terdampak |
|---|------|:------------:|----------------|
| V4-1 | Fix thread n-1 — `max(1, cpu_count - 1)`, hapus batas maks 8 | 🟢 Low | `core/env.py` |
| V4-2 | Auto GPU detect untuk Video pipeline — pakai `video_encoder_flags()` yang sudah ada | 🟢 Low | `api/video.py`, `core/env.py` |
| V4-3 | Collapsible section di tab Video (Crop, Fade, XFade) | 🟡 Medium | `index.html`, `panel-video.js`, `style.css` |
| V4-4 | Tab Merge default source = Sound Layer Output | 🟢 Low | `panel-merge.js` |
| V4-5 | Toggle Optional Sound Pool (section tersembunyi by default) | 🟢 Low | `index.html`, `panel-sound-layer.js` |
| V4-6 | Optional Sound dual-mode: Folder ATAU File Individual | 🟡 Medium | `index.html`, `panel-sound-layer.js`, `api/sound_layer.py` |
| V4-7 | Auto Cleanup temp files — endpoint baru + tombol di sidebar | 🟠 Medium-High | `api/cleanup.py` (baru), `api/router.py`, `index.html` |

### ❌ Out-of-Scope (v4 → ditunda v5)

- Preset/Profile system (simpan komposisi layer)
- GPU acceleration untuk audio processing (FFmpeg audio tetap CPU-based)
- GPU acceleration untuk Merge (saat ini pakai `-c:v copy`, tidak butuh encode ulang)
- Ping-pong/Boomerang video loop
- Batch multi-select file untuk Optional Pool
- Schedule/auto cleanup per hari/sesi

---

## 6. User Stories & Acceptance Criteria

### V4-1 — Thread n-1

> *As a user dengan PC 4-core, I want FFmpeg tidak memakai semua core, so that PC saya tidak freeze saat render panjang.*

**AC:**
- `get_thread_flags()` mengembalikan `max(1, cpu_count() - 1)` untuk `-filter_threads` dan `-filter_complex_threads`
- Nilai minimum adalah 1 (tidak pernah 0)
- Hapus pembatasan `min(8, ...)` — di 12-core hasilnya 11 thread, bukan 8
- Contoh: 4-core → 3 thread | 8-core → 7 thread | 1-core → 1 thread

---

### V4-2 — Auto GPU Encoder untuk Video

> *As a user dengan GPU NVIDIA, I want Video pipeline otomatis pakai GPU, so that render lebih cepat.*

**AC:**
- Semua fungsi encoder di `api/video.py` menggunakan `video_encoder_flags()` dari `core/env.py` (yang sudah punya logika NVENC)
- Fungsi terdampak: `cmd_crop`, `cmd_upscale`, `cmd_fade_video`, dan enc_flags dalam `cmd_loop_xfade`
- Jika `USE_NVENC = True`: encoder = `h264_nvenc`, `-cq 23`, `-preset p4`
- Jika `USE_NVENC = False`: encoder = `libx264`, `-crf 23`, `-preset fast` (sama seperti saat ini)
- Log pipeline menampilkan encoder yang digunakan (contoh: "⚡ Encoder: h264_nvenc" atau "🖥 Encoder: libx264")
- **Merge tidak berubah** — tetap `-c:v copy` (tidak perlu GPU karena tidak ada re-encode video)
- **Catatan penting**: `USE_NVENC` di `core/env.py` saat ini hanya aktif di Colab (`IS_COLAB and _check_nvenc()`). Untuk lokal Windows, logika ini perlu diubah menjadi `_check_nvenc()` saja (tanpa syarat `IS_COLAB`). `_check_nvenc()` sudah aman karena pakai `@lru_cache` dan return `False` jika tidak ada GPU.

---

### V4-3 — Collapsible Section di Tab Video

> *As a user, I want section Crop, Fade, dan XFade bisa dikollaps di tab Video, so that tombol Proses langsung terlihat tanpa scroll.*

**AC:**
- Tiga section dikollaps dengan header yang bisa diklik:
  - **Crop & Upscale** — default: **expand** (sering dipakai)
  - **Fade In / Fade Out** — default: **collapsed**
  - **Loop Transition XFade** — default: **collapsed**
- Header menampilkan summary nilai aktif saat collapsed:
  - Crop: "T:0 B:0 L:0 R:0 | FHD" atau "✓ Crop aktif"
  - Fade: "OFF" atau "In:3s Out:3s"
  - XFade: "OFF" atau "1.0s / fade"
- Animasi smooth: CSS `max-height` transition 250ms ease
- Chevron icon rotates 180° saat expanded
- Tidak ada perubahan pada logika submit/render

---

### V4-4 — Merge Default Sound Layer Output

> *As a user, I want tab Merge langsung siap dengan Sound Layer Output setelah saya render Sound Layer, so that tidak perlu klik extra.*

**AC:**
- Default radio yang aktif saat membuka tab Merge adalah **"Sound Layer Output"**, bukan "Manual Layers"
- Jika `AppState.soundLayerOutputPath` sudah ada (setelah render), field otomatis terisi
- Jika belum ada, tampilkan hint: *"Render Sound Layer terlebih dahulu, atau gunakan Manual Layers"*
- Manual Layers **tetap ada** dan tetap bisa dipakai
- Perubahan hanya pada nilai `checked` default di HTML atau inisialisasi di `initMerge()`

---

### V4-5 — Toggle Optional Sound Pool

> *As a user, I want section Optional Sound Pool tersembunyi by default di tab Sound Layer, so that UI terasa lebih ringkas.*

**AC:**
- Checkbox "Aktifkan Optional Sound Pool" tampil di atas section
- Default: **unchecked** (section dalam state `ctrl-off`)
- Saat unchecked: `optional_sounds_folder: ""` dan `included_files: []` dikirim ke backend
- Preview Mix dan Render Full **tetap aktif** meski Optional Pool tidak dicentang
- Plan Layers ("🎲 Plan Layers") **tidak bisa diklik** jika Optional Pool dicentang tapi folder/file belum dipilih → toast warning

---

### V4-6 — Optional Sound Dual-Mode (Folder + File Individual)

> *As a user, I want bisa pilih file audio individual ATAU seluruh folder untuk Optional Sound Pool, so that saya lebih fleksibel.*

**AC:**
- Di dalam `#optionalSoundControls`, terdapat dua mode via **radio button**:
  - **Mode Folder** (default saat Optional Pool diaktifkan) — browse folder → scan → checklist
  - **Mode File** — browse satu atau lebih file individual; tampilkan daftar dengan nama, durasi, dan tombol hapus `[×]` per item
- Kedua mode menghasilkan array `included_files: [path1, path2, ...]` yang sama ke backend
- Di Mode File: bisa tambah file satu per satu (klik tombol "+ Tambah File Audio" berulang kali)
- Di Mode File: file yang sudah ditambah bisa dihapus satu per satu
- Backend `api/sound_layer.py` **tidak perlu diubah** — sudah menerima `included_files` array
- Mode File menggunakan endpoint browse audio existing (`browseAudio()`) — satu file per klik

---

### V4-7 — Auto Cleanup Temp Files

> *As a user, I want bisa membersihkan file temporary dengan satu klik, so that disk saya tidak penuh.*

**AC:**
- Tombol **"🗑 Clear Temp"** muncul di bagian bawah sidebar (di bawah `sidebar-workspace`)
- Saat diklik: tampilkan toast konfirmasi dengan jumlah file + total ukuran yang akan dihapus
  - Contoh: *"12 file temp ditemukan (1.2 GB) — Hapus?"* dengan tombol **Hapus** / **Batal**
- Setelah dikonfirmasi: panggil `POST /cleanup`, tampilkan hasil di toast success
- Endpoint `POST /cleanup`:
  - Input: `{ workspace: string }`
  - Pattern yang dihapus: `_tmp_*`, `*._preview_mix*`, `*._layered.*`, `_tmp_xblk*`, `_tmp_xconcat*`
  - **TIDAK hapus**: `*._final.*` (output utama user)
  - **TIDAK hapus**: file di luar folder workspace (path traversal guard)
  - Output: `{ deleted: int, freed_bytes: int, freed_str: string, files: [list] }`
- Endpoint `GET /cleanup/scan` tersedia untuk preview tanpa menghapus
- Jika tidak ada file temp: toast info "Tidak ada file temporary yang perlu dibersihkan"
- Cleanup hanya berlaku di **workspace aktif** (`AppState.workspace`)

---

## 7. Functional Requirements Detail

### FR — core/env.py (V4-1 + V4-2)

```python
# V4-1: Ubah get_thread_flags()
# SEBELUM:
recommended_threads = str(min(8, logical_cpu))
# SESUDAH:
recommended_threads = str(max(1, logical_cpu - 1))

# V4-2: Aktifkan NVENC di lokal (tidak hanya Colab)
# SEBELUM:
USE_NVENC: bool = IS_COLAB and _check_nvenc()
# SESUDAH:
USE_NVENC: bool = _check_nvenc()
```

---

### FR — api/video.py (V4-2)

Ganti semua blok encoder hardcoded dengan `video_encoder_flags()`:

```python
from core.env import get_thread_flags, video_encoder_flags, USE_NVENC

# cmd_crop, cmd_upscale, cmd_fade_video:
# Ganti: ["-c:v","libx264","-crf","23","-preset","fast","-pix_fmt","yuv420p","-movflags","+faststart"]
# Dengan: [*video_encoder_flags(crf=23, preset="fast")]

# cmd_loop_xfade — enc_flags block:
# NVENC tidak support -profile:v high + -level 4.1, perlu conditional:
if USE_NVENC:
    enc_flags = video_encoder_flags(crf=23, preset="fast")
else:
    enc_flags = [
        "-c:v", "libx264", "-profile:v", "high", "-level", "4.1",
        "-pix_fmt", "yuv420p", "-crf", "23", "-preset", "fast",
        "-movflags", "+faststart",
    ]
```

Tambahkan log encoder di `video_pipeline()`:

```python
from core.env import USE_NVENC
encoder_name = "h264_nvenc ⚡" if USE_NVENC else "libx264 🖥"
yield f"data: {json.dumps({'log': f'Encoder: {encoder_name}'})}\\n\\n"
```

---

### FR — index.html + style.css (V4-3)

Struktur HTML collapsible untuk tab Video:

```html
<div class="collapsible-section">
  <button class="section-toggle" id="toggleCrop" aria-expanded="true">
    <span class="section-title">✂ Crop &amp; Upscale</span>
    <span class="section-summary" id="cropSummary">T:0 B:0 L:0 R:0</span>
    <svg class="toggle-chevron" width="14" height="14" viewBox="0 0 24 24"
         fill="none" stroke="currentColor" stroke-width="2">
      <polyline points="6 9 12 15 18 9"/>
    </svg>
  </button>
  <div class="section-body open" id="cropBody">
    <!-- existing crop + upscale content -->
  </div>
</div>
```

CSS tambahan di `style.css`:

```css
.collapsible-section {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 8px;
  overflow: hidden;
}
.section-toggle {
  width: 100%; display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; background: var(--bg-card); border: none;
  cursor: pointer; color: var(--text); font-size: 13px; font-weight: 500;
  transition: background 160ms var(--ease);
}
.section-toggle:hover { background: var(--bg-hover); }
.section-summary {
  margin-left: auto; font-size: 11px;
  color: var(--text-muted); font-family: var(--font-mono);
}
.toggle-chevron { flex-shrink: 0; transition: transform 250ms ease; }
.section-toggle[aria-expanded="true"] .toggle-chevron { transform: rotate(180deg); }
.section-body {
  overflow: hidden;
  max-height: 0;
  transition: max-height 250ms ease;
  padding: 0 14px;
}
.section-body.open {
  max-height: 800px;
  padding: 0 14px 14px;
}
```

---

### FR — panel-video.js (V4-3)

```javascript
function initCollapsible(toggleId, bodyId, defaultOpen = false) {
  const toggle = document.getElementById(toggleId);
  const body   = document.getElementById(bodyId);
  if (!toggle || !body) return;
  if (defaultOpen) {
    body.classList.add("open");
    toggle.setAttribute("aria-expanded", "true");
  }
  toggle.addEventListener("click", () => {
    const isOpen = body.classList.toggle("open");
    toggle.setAttribute("aria-expanded", String(isOpen));
  });
}

// Crop: default open — Fade & XFade: default closed
initCollapsible("toggleCrop",   "cropBody",   true);
initCollapsible("toggleFade",   "fadeBody",   false);
initCollapsible("toggleXfade",  "xfadeBody",  false);

// Summary updaters
function updateCropSummary() {
  const t = document.getElementById("cropTop").value    || "0";
  const b = document.getElementById("cropBottom").value || "0";
  const l = document.getElementById("cropLeft").value   || "0";
  const r = document.getElementById("cropRight").value  || "0";
  const res = document.getElementById("upscaleRes").value;
  const resLabel = res ? res.replace(":", "×") : "—";
  document.getElementById("cropSummary").textContent =
    `T:${t} B:${b} L:${l} R:${r} | ${resLabel}`;
}
function updateFadeSummary() {
  const fi = document.getElementById("videoFadeInEnabled").checked;
  const fo = document.getElementById("videoFadeOutEnabled").checked;
  if (!fi && !fo) { document.getElementById("fadeSummary").textContent = "OFF"; return; }
  const parts = [];
  if (fi) parts.push(`In:${document.getElementById("videoFadeInDuration").value}s`);
  if (fo) parts.push(`Out:${document.getElementById("videoFadeOutDuration").value}s`);
  document.getElementById("fadeSummary").textContent = parts.join(" ");
}
function updateXfadeSummary() {
  const en = document.getElementById("videoXfadeEnabled").checked;
  document.getElementById("xfadeSummary").textContent = en
    ? `${document.getElementById("videoXfadeDuration").value}s / ${document.getElementById("videoXfadeType").value}`
    : "OFF";
}
// Attach to inputs
["cropTop","cropBottom","cropLeft","cropRight","upscaleRes"]
  .forEach(id => document.getElementById(id)?.addEventListener("input", updateCropSummary));
["videoFadeInEnabled","videoFadeOutEnabled","videoFadeInDuration","videoFadeOutDuration"]
  .forEach(id => document.getElementById(id)?.addEventListener("change", updateFadeSummary));
["videoXfadeEnabled","videoXfadeDuration","videoXfadeType"]
  .forEach(id => document.getElementById(id)?.addEventListener("change", updateXfadeSummary));
// Init summaries on load
updateCropSummary(); updateFadeSummary(); updateXfadeSummary();
```

---

### FR — panel-merge.js (V4-4)

```javascript
export function initMerge() {
  // Ubah default: Sound Layer Output menjadi pilihan awal
  const radioLayer = document.getElementById("mergeAudioSourceLayer");
  if (radioLayer) radioLayer.checked = true;
  syncMergeAudioSource(); // trigger UI sesuai default baru
  // ... sisa init tidak berubah
}
```

---

### FR — index.html + panel-sound-layer.js (V4-5 + V4-6)

**V4-5 — HTML toggle wrapper:**

```html
<!-- Ganti blok Optional Sound Pool yang ada -->
<div class="section-divider"></div>
<div class="field-group">
  <div class="checkbox-row" style="margin-bottom:10px;">
    <label class="checkbox-label">
      <input type="checkbox" id="soundLayerOptionalEnabled">
      <span class="checkmark"></span>Aktifkan Optional Sound Pool
    </label>
  </div>
  <div class="ctrl-field ctrl-off" id="optionalSoundControls">
    <!-- V4-6: mode selector -->
    <div style="display:flex;gap:16px;margin-bottom:12px;">
      <label class="checkbox-label">
        <input type="radio" name="optionalMode" value="folder" checked>
        <span class="checkmark" style="border-radius:50%"></span> Folder
      </label>
      <label class="checkbox-label">
        <input type="radio" name="optionalMode" value="files">
        <span class="checkmark" style="border-radius:50%"></span> File Individual
      </label>
    </div>
    <!-- Mode Folder (existing) -->
    <div id="optionalFolderMode">
      <label class="field-label">Optional Sound Pool Folder</label>
      <div class="file-row">
        <input type="text" id="soundLayerFolder" class="file-input"
               placeholder="Pilih folder berisi suara opsional..." readonly>
        <button class="btn btn-secondary" id="soundLayerFolderBrowse">Browse Folder</button>
      </div>
      <div id="soundLayerPoolContainer" class="pool-container hidden">
        <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;
                    display:flex;justify-content:space-between;align-items:center;">
          <span>Pilih file untuk digunakan sebagai pool:</span>
          <div>
            <button class="btn btn-ghost btn-add"
                    style="padding:2px 6px;font-size:10px;" id="soundLayerPoolAll">All</button>
            <button class="btn btn-ghost btn-add"
                    style="padding:2px 6px;font-size:10px;margin-left:4px;"
                    id="soundLayerPoolNone">None</button>
          </div>
        </div>
        <div id="soundLayerPoolList"></div>
      </div>
    </div>
    <!-- Mode File Individual (baru) -->
    <div id="optionalFilesMode" class="hidden">
      <label class="field-label">File Audio Individual</label>
      <div id="optionalIndividualFileList"
           style="display:flex;flex-direction:column;gap:6px;margin-bottom:8px;"></div>
      <button class="btn btn-ghost btn-add" id="optionalAddFile">
        + Tambah File Audio
      </button>
    </div>
  </div>
</div>
```

**V4-5 + V4-6 — JS additions di `initSoundLayer()`:**

```javascript
// V4-5: pastikan ctrl-off aktif by default saat init
document.getElementById("optionalSoundControls")?.classList.add("ctrl-off");

document.getElementById("soundLayerOptionalEnabled")
  ?.addEventListener("change", e => {
    document.getElementById("optionalSoundControls")
      ?.classList.toggle("ctrl-off", !e.target.checked);
  });

// V4-6: mode switcher
document.querySelectorAll("input[name='optionalMode']").forEach(radio => {
  radio.addEventListener("change", e => {
    document.getElementById("optionalFolderMode")
      ?.classList.toggle("hidden", e.target.value !== "folder");
    document.getElementById("optionalFilesMode")
      ?.classList.toggle("hidden", e.target.value !== "files");
  });
});

// V4-6: Add individual file
AppState.optionalIndividualFiles = [];

document.getElementById("optionalAddFile")
  ?.addEventListener("click", async () => {
    try {
      const path = await browseAudio();
      if (!path) return;
      const probe = await probeFile(path);
      const dur   = probe?.duration ?? 0;
      const name  = path.split(/[/\\]/).pop();
      AppState.optionalIndividualFiles.push({ path, name, duration: dur });
      renderIndividualFileList();
    } catch (e) {
      toast("Gagal menambah file: " + e.message, "error");
    }
  });

function renderIndividualFileList() {
  const list = document.getElementById("optionalIndividualFileList");
  if (!list) return;
  list.innerHTML = "";
  AppState.optionalIndividualFiles.forEach((f, idx) => {
    const div = document.createElement("div");
    div.className = "pool-item";
    div.innerHTML = `
      <span class="pool-item-name" title="${f.path}">${f.name}</span>
      <span class="pool-item-dur">${f.duration.toFixed(1)}s</span>
      <button class="btn btn-ghost"
              style="color:var(--danger);padding:2px 6px;margin-left:auto;"
              data-idx="${idx}">×</button>
    `;
    div.querySelector("button").addEventListener("click", () => {
      AppState.optionalIndividualFiles.splice(idx, 1);
      renderIndividualFileList();
    });
    list.appendChild(div);
  });
}

// Helper: ambil included_files dari mode aktif
function getIncludedFiles() {
  const optEnabled = document.getElementById("soundLayerOptionalEnabled")?.checked;
  if (!optEnabled) return [];
  const mode = document.querySelector("input[name='optionalMode']:checked")?.value;
  if (mode === "files") {
    return AppState.optionalIndividualFiles.map(f => f.path);
  }
  return Array.from(
    document.querySelectorAll("#soundLayerPoolList .pool-checkbox:checked")
  ).map(cb => cb.dataset.path);
}
```

Ganti pengambilan `includedFiles` di payload dengan `getIncludedFiles()`.

---

### FR — api/cleanup.py (V4-7, file baru)

```python
"""Auto Cleanup — hapus file temporary di workspace."""
import os
import fnmatch
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["cleanup"])

TEMP_PATTERNS   = ["_tmp_*", "*._preview_mix*", "*._layered.*",
                   "_tmp_xblk*", "_tmp_xconcat*"]
SAFE_PATTERNS   = ["*._final.*"]   # TIDAK pernah dihapus


def _scan(workspace: str) -> list[dict]:
    workspace = os.path.realpath(workspace)
    result = []
    for fname in os.listdir(workspace):
        fpath = os.path.realpath(os.path.join(workspace, fname))
        if not fpath.startswith(workspace + os.sep) and fpath != workspace:
            continue  # path traversal guard
        if any(fnmatch.fnmatch(fname, p) for p in SAFE_PATTERNS):
            continue
        if any(fnmatch.fnmatch(fname, p) for p in TEMP_PATTERNS):
            try:
                size = os.path.getsize(fpath)
                result.append({"path": fpath, "name": fname, "size": size})
            except Exception:
                pass
    return result


def _fmt(b: int) -> str:
    if b >= 1024**3: return f"{b/1024**3:.2f} GB"
    if b >= 1024**2: return f"{b/1024**2:.1f} MB"
    return f"{b/1024:.0f} KB"


@router.get("/cleanup/scan")
async def scan_temp(workspace: str = ""):
    if not workspace or not os.path.isdir(workspace):
        return JSONResponse({"error": "Workspace tidak valid"}, status_code=400)
    files = _scan(workspace)
    total = sum(f["size"] for f in files)
    return {
        "files": [{"name": f["name"], "size_str": _fmt(f["size"])} for f in files],
        "total": len(files),
        "total_str": _fmt(total),
    }


@router.post("/cleanup")
async def cleanup_temp(request: Request):
    data      = await request.json()
    workspace = data.get("workspace", "").strip()
    if not workspace or not os.path.isdir(workspace):
        return JSONResponse({"error": "Workspace tidak valid"}, status_code=400)

    files   = _scan(workspace)
    deleted = 0
    freed   = 0
    names   = []
    for f in files:
        try:
            os.remove(f["path"])
            freed   += f["size"]
            deleted += 1
            names.append(f["name"])
        except Exception:
            pass

    return {"deleted": deleted, "freed_bytes": freed,
            "freed_str": _fmt(freed), "files": names}
```

Daftarkan di `api/router.py`:
```python
from api.cleanup import router as cleanup_router
app.include_router(cleanup_router)
```

---

### FR — Sidebar Cleanup Button (V4-7)

**HTML** (setelah `.sidebar-workspace`):
```html
<div class="sidebar-cleanup">
  <button class="btn-cleanup" id="sidebarCleanupBtn"
          title="Bersihkan file temporary di workspace">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" stroke-width="1.8">
      <polyline points="3 6 5 6 21 6"/>
      <path d="M19 6l-1 14H6L5 6"/>
      <path d="M10 11v6"/><path d="M14 11v6"/>
      <path d="M9 6V4h6v2"/>
    </svg>
    <span>Clear Temp</span>
  </button>
</div>
```

**CSS** (tambahkan ke `style.css`):
```css
.sidebar-cleanup { padding: 0 8px 14px; flex-shrink: 0; }
.btn-cleanup {
  display: flex; align-items: center; gap: 7px;
  width: 100%; padding: 6px 10px; border-radius: var(--radius-sm);
  border: 1px solid var(--border); background: transparent;
  color: var(--text-muted); font-size: 12px; cursor: pointer;
  transition: all 160ms var(--ease); font-family: var(--font-body);
}
.btn-cleanup:hover {
  background: rgba(239,68,68,0.08);
  color: #f87171;
  border-color: rgba(239,68,68,0.3);
}
```

**JS** (di `main.js` atau file util baru):
```javascript
document.getElementById("sidebarCleanupBtn")?.addEventListener("click", async () => {
  const ws = AppState.workspace;
  if (!ws) { toast("Set workspace terlebih dahulu", "warning"); return; }

  // Scan dulu
  const res = await fetch(`/cleanup/scan?workspace=${encodeURIComponent(ws)}`);
  const data = await res.json();

  if (data.total === 0) {
    toast("Tidak ada file temporary yang perlu dibersihkan ✓", "info");
    return;
  }

  // Toast konfirmasi
  toast(
    `${data.total} file temp ditemukan (${data.total_str}) — hapus?`,
    "warning",
    {
      action: "Hapus",
      onAction: async () => {
        const r = await fetch("/cleanup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workspace: ws }),
        });
        const d = await r.json();
        toast(`✓ ${d.deleted} file dihapus (${d.freed_str} dibebaskan)`, "success");
      }
    }
  );
});
```

> **Catatan:** Implementasi `toast` dengan action button mungkin butuh update `ui.js` jika belum support. Jika belum, gunakan `confirm()` native browser sebagai fallback sementara.

---

## 8. Non-Functional Requirements

| Aspek | Requirement |
|-------|-------------|
| **Performance** | Collapsible section tidak boleh menyebabkan layout shift (CLS = 0) |
| **Security** | Cleanup hanya boleh menghapus file di dalam path workspace aktif; wajib `os.path.realpath()` + prefix check |
| **GPU Fallback** | Jika NVENC error mid-render, log error informatif + lanjutkan dengan libx264 |
| **Backward Compat** | Backend endpoint `/merge`, `/video/pipeline`, `/sound-layer/render` tidak berubah signature |
| **Error Handling** | Jika Sound Layer Output belum ada saat default ke mode tersebut di Merge, tampilkan hint yang jelas |
| **Accessibility** | Semua toggle/collapsible bisa dioperasikan keyboard; `aria-expanded` attribute wajib |

---

## 9. Technical Considerations

### 9.1 Kenapa Merge Tidak Butuh GPU

`api/merge.py` menggunakan `-c:v copy` — video stream tidak di-encode ulang. GPU encode hanya relevan saat ada proses encode video baru. Memaksa GPU di merge berarti video harus di-decode lalu di-encode ulang → kualitas turun, waktu tambah, tanpa manfaat nyata. Kesimpulan: **merge tetap `-c:v copy`**, GPU hanya untuk Video pipeline.

### 9.2 USE_NVENC Scope Fix

```python
# core/env.py — sebelum:
USE_NVENC: bool = IS_COLAB and _check_nvenc()
# sesudah:
USE_NVENC: bool = _check_nvenc()
```

`_check_nvenc()` sudah aman: pakai `@lru_cache(maxsize=1)`, cek `shutil.which("ffmpeg")` terlebih dahulu, dan return `False` jika tidak ada GPU atau FFmpeg tidak support NVENC. Tidak ada risiko error.

### 9.3 NVENC Profile di XFade

`cmd_loop_xfade` saat ini set `-profile:v high -level 4.1` yang **tidak kompatibel dengan NVENC default**. Solusi: conditional enc_flags:

```python
from core.env import USE_NVENC, video_encoder_flags

if USE_NVENC:
    enc_flags = video_encoder_flags(crf=23, preset="fast")
    # video_encoder_flags untuk NVENC tidak include -profile:v / -level
else:
    enc_flags = [
        "-c:v", "libx264", "-profile:v", "high", "-level", "4.1",
        "-pix_fmt", "yuv420p", "-crf", "23", "-preset", "fast",
        "-movflags", "+faststart",
    ]
```

### 9.4 CSS max-height untuk Collapsible

Nilai `max-height: 800px` cukup generous untuk semua section. Jangan gunakan `max-height: 100%` karena tidak bekerja dengan CSS `transition`. Padding perlu di-handle (0 saat collapsed, nilai normal saat open) untuk menghindari jump.

### 9.5 Optional Sound Backend Sudah Siap

`api/sound_layer.py` endpoint `/preview` dan `/render` sudah menerima `included_files` sebagai array path langsung. Mode File di V4-6 hanya perlu mengirim array ini tanpa `optional_sounds_folder`. **Tidak ada perubahan backend untuk V4-6.**

### 9.6 Toast dengan Action Button

Implementasi cleanup di `main.js` membutuhkan `toast()` yang support action callback. Jika `ui.js` belum support, gunakan `window.confirm()` sebagai fallback sementara, kemudian upgrade `toast` di iterasi berikutnya.

---

## 10. UI/UX Wireframe Notes

### Tab Video — After V4-3

```
┌─────────────────────────────────────────────────┐
│ Video Pipeline                 Crop → Upscale → Loop │
├─────────────────────────────────────────────────┤
│ 📁 File Video: [___________________] [Browse]   │
│                                                 │
│ ▼ ✂ Crop & Upscale    T:0 B:0 L:0 R:0 | —  [▼]│ ← OPEN (default)
│   [Crop grid: Top/Bottom/Left/Right + Upscale]  │
│                                                 │
│ ▶ 🌅 Fade In / Fade Out              OFF   [▼] │ ← COLLAPSED
│                                                 │
│ ▶ 🔄 Loop XFade                      OFF   [▼] │ ← COLLAPSED
│                                                 │
│ ☑ Pertahankan suara original                    │
│ Output: [auto]                                  │
│ [▶ Proses Video]                                │
└─────────────────────────────────────────────────┘
```

### Tab Merge — After V4-4

```
┌─────────────────────────────────────────────────┐
│ Merge Final                                     │
├─────────────────────────────────────────────────┤
│ 📁 File Video: [___________________] [Browse]   │
│                                                 │
│ Sumber Audio:                                   │
│   ○ Manual Layers    ● Sound Layer Output ← DEFAULT
│                                                 │
│   🎵 /path/to/output.m4a  ← auto-filled         │
│   ℹ Belum ada — render Sound Layer terlebih dahulu
│                                                 │
│ Output: [auto]                                  │
│ [▶ Merge]                                       │
└─────────────────────────────────────────────────┘
```

### Tab Sound Layer — Optional Pool V4-5 + V4-6

```
┌─────────────────────────────────────────────────┐
│ ... (Main Sounds, Durasi, Format, XFade) ...    │
│ ─────────────────────────────────────────────── │
│ ☐ Aktifkan Optional Sound Pool                  │ ← default unchecked
│                                                 │
│  [section di bawah GREY/disabled jika uncheck]  │
│   ○ Folder    ● File Individual                 │
│                                                 │
│   [+ Tambah File Audio]                         │
│   • paper_crinkle.wav   12.3s  [×]              │
│   • wind_soft.mp3        8.7s  [×]              │
│                                                 │
│  [Jumlah Kejadian] [Gap] [Window] [Duration]    │
└─────────────────────────────────────────────────┘
```

### Sidebar — After V4-7

```
┌─ Sidebar ─────────────────────┐
│  [Logo] ASMR Tools            │
│  ───────────────────          │
│  > Video                      │
│  > Extract                    │
│  > Sound Layer                │
│  > Denoise                    │
│  > Merge                      │
│  > Thumbnail                  │
│  ───────────────────          │
│  Workspace                    │
│  /path/to/workspace           │
│  ───────────────────          │
│  [🗑 Clear Temp]              │ ← tombol baru
└───────────────────────────────┘
```

---

## 11. Dependencies & Risks

| # | Risk | Dampak | Mitigasi |
|---|------|--------|----------|
| R1 | NVENC tidak support `-profile:v high` + `-level 4.1` yang ada di xfade | Render error/crash | Conditional enc_flags per encoder type (§9.3) ✅ sudah dirancang |
| R2 | Cleanup menghapus file penting | Data loss | Whitelist `*._final.*`; path realpath + prefix check; konfirmasi sebelum hapus |
| R3 | CSS `max-height` transition terpotong di konten besar | Section terpotong | Set max-height: 800px generous; test di viewport 768px |
| R4 | Merge default Sound Layer — path kosong tidak di-handle | Error diam | Validasi + hint jelas di `syncMergeAudioSource()` |
| R5 | `_check_nvenc()` dipanggil tapi FFmpeg tidak tersedia | ImportError / crash | Sudah ada guard `shutil.which("ffmpeg")` ✅ |
| R6 | Toast dengan action button belum ada di `ui.js` | Cleanup flow rusak | Fallback ke `window.confirm()` sementara |

---

## 12. Urutan Implementasi (Milestones)

Diurutkan dari risiko terendah ke tertinggi:

| M | Item | Estimasi | Catatan |
|---|------|----------|---------|
| M1 | V4-1: Thread n-1 (`core/env.py`) | ~5 mnt | 1 baris, zero risk |
| M2 | V4-2: USE_NVENC fix + `api/video.py` ganti encoder | ~30 mnt | Perlu conditional xfade |
| M3 | V4-4: Merge default Sound Layer (`panel-merge.js`) | ~10 mnt | 2–3 baris |
| M4 | V4-5: Optional Sound toggle (`index.html` + JS) | ~20 mnt | CSS `ctrl-off` sudah ada |
| M5 | V4-3: Collapsible Video sections (HTML + JS + CSS) | ~60 mnt | Paling banyak perubahan HTML |
| M6 | V4-6: Optional Sound dual-mode (HTML + JS) | ~60 mnt | State array baru di AppState |
| M7 | V4-7: Auto Cleanup (`api/cleanup.py`, router, sidebar) | ~90 mnt | Butuh review keamanan path |

**Total estimasi: ~4–5 jam implementasi penuh.**

---

## 13. Open Questions

| # | Pertanyaan | Default Usulan |
|---|------------|----------------|
| OQ-1 | Toast action button — upgrade `ui.js` sekaligus, atau pakai `confirm()` dulu? | `confirm()` fallback dulu, upgrade toast di M7 |
| OQ-2 | Ada suffix/pattern temp lain yang perlu ditambahkan ke cleanup? | Konfirmasi setelah cek output nyata di disk |
| OQ-3 | V4-6 Mode File: multi-browse sekaligus (satu per satu saja, atau butuh multi-select)? | Satu per satu; multi-select di v5 |
| OQ-4 | V4-4 Merge: volume Sound Layer Output bisa diatur, atau selalu 100%? | 100% untuk sekarang |
| OQ-5 | V4-2 GPU: badge visual "⚡ GPU" di header tab Video saat NVENC aktif? | Ya, tapi opsional — bisa di log saja |

---

## Ringkasan Eksekutif

### Top 3 Risiko
1. **NVENC profile incompatibility di XFade** (R1) — wajib conditional enc_flags, jangan lupa
2. **Cleanup data loss** (R2) — whitelist + path traversal guard adalah syarat mutlak
3. **Merge default kosong** (R4) — hint yang jelas mencegah user bingung

### MVP v4 (harus ada sebelum release)
- ✅ V4-1: Thread n-1
- ✅ V4-2: Auto GPU Video (dengan fallback CPU)
- ✅ V4-4: Merge default Sound Layer
- ✅ V4-5: Optional Sound toggle

### Bisa Ditunda ke v4.1
- V4-3: Collapsible Video sections (UX improvement, bukan blocking)
- V4-6: Optional Sound dual-mode (folder masih cukup untuk kebanyakan use case)
- V4-7: Auto Cleanup (tidak urgent, tapi sangat membantu jangka panjang)

---

*Apakah ada bagian yang perlu diubah atau ditambahkan?*
