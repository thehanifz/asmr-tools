# Update Manual: Aktifkan Log Handler Baru

## Yang Sudah Selesai

✅ **Backend (`api/utils.py`)**
- `run_ffmpeg_stream()` sekarang kirim:
  - `ts` (timestamp HH:MM:SS)
  - `elapsed` (detik sejak mulai)
  - `status: 'start' | 'ping' | 'done' | 'error'`
  - Heartbeat ping tiap 3 detik

✅ **Frontend (`frontend/js/log-handler.js`)**
- `window.runSSE(url, payload, logBox, statusEl, onDone)` — universal SSE runner
- `window.enhancedLog(logBox, statusEl, data)` — render log dengan timestamp + elapsed
- Format log: `[16:04:23] (2m 15s) ffmpeg version...`
- Status indikator: 🔄 Running · 2m 15s → ✅ Done · 3m 42s

---

## Yang Perlu Kamu Lakukan

### 1. Edit `index.html` — Tambah 1 Baris

Buka `index.html`, cari baris **sebelum `</body>`** (sekitar baris 427), tambahkan:

```html
<script src="/js/log-handler.js"></script>
</body>
```

Atau pakai find-replace:

**Find:**
```
</body>
```

**Replace:**
```
<script src="/js/log-handler.js"></script>
</body>
```

### 2. Update Fungsi-Fungsi Existing (Opsional — Bisa Nanti)

Jika mau langsung pakai enhanced log di semua panel, cari fungsi seperti `runExtractAudio()`, `runVideoProcess()`, dll. yang pakai manual `fetch + reader.read()`, ganti jadi:

**Sebelum:**
```javascript
const res = await fetch('/api/extract-audio', {...});
const reader = res.body.getReader();
while (true) {
  const {done, value} = await reader.read();
  ...
}
```

**Sesudah:**
```javascript
await window.runSSE(
  '/api/extract-audio',
  { input_path: inputPath, output_path: outputPath, format: fmt, workspace },
  document.getElementById('log-box'), // log box
  document.getElementById('progress-info'), // status element
  (data) => {
    // callback saat done/error
    if (data.status === 'done') {
      alert('Selesai!');
    }
  }
);
```

---

## Test

1. `git pull`
2. Edit `index.html` (tambah 1 baris `<script>`)
3. `start.bat`
4. Buka `http://localhost:8000`
5. Coba proses video/audio — log sekarang ada timestamp + elapsed timer!

---

## Preview Log Baru

```
[16:04:23] ▶️ Memulai proses...
[16:04:23] (0s) ffmpeg version 8.1-full_build...
[16:04:25] (2s) Input #0, mov,mp4,m4a,3gp...
[16:04:27] (4s) Stream mapping...
[16:05:30] (67s) frame= 1024 fps=24 q=-1.0 Lsize=...
[16:06:05] (1m 42s) ✅ Proses selesai (OK)
```

**Status indicator:**
- 🔄 Running · 1m 42s (update tiap 3 detik, meskipun tidak ada log baru)
- ✅ Done · 3m 20s
- ❌ Error · 45s
