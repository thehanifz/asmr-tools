// ═══════════════════════════════════════════════
//  Panel: Audio Loop
// ═══════════════════════════════════════════════
import { AppState, setWorkspace, buildOutputPath } from './state.js';
import { browseAudio, probeFile }                  from './api.js';
import { toast, showFileInfo, consumeSSE }         from './ui.js';

const FORMAT_EXT = { mp3: '.mp3', aac: '.m4a', flac: '.flac', wav: '.wav' };

// ── Helpers ─────────────────────────────────
function $(id) { return document.getElementById(id); }

function val(id, fallback = '') {
  const el = $(id);
  return el ? el.value : fallback;
}

function updateDurationLabel() {
  const sec = parseInt(val('audioDuration', '3600')) || 0;
  const h   = Math.floor(sec / 3600);
  const m   = Math.floor((sec % 3600) / 60);
  const s   = sec % 60;
  let lbl;
  if (h > 0) {
    lbl = `= ${h} jam${m > 0 ? ' ' + m + ' mnt' : ''}`;
  } else if (m > 0) {
    lbl = `= ${m} menit${s > 0 ? ' ' + s + ' dtk' : ''}`;
  } else {
    lbl = `= ${s} detik`;
  }
  const el = $('audioDurationLabel');
  if (el) el.textContent = lbl;
}

function syncOutputExt() {
  const input  = val('audioInput');
  const fmt    = val('audioFormat', 'aac');
  const outEl  = $('audioOutput');
  if (!outEl) return;
  if (input) {
    outEl.value = buildOutputPath(input, '._looped', FORMAT_EXT[fmt] || '.m4a');
  }
}

// ── Init ──────────────────────────────────
export function initAudio() {

  // Pastikan semua elemen ada
  const IDS = ['audioBrowse','audioProcess','audioDuration',
               'audioFormat','audioXfade','audioInput','audioOutput'];
  for (const id of IDS) {
    if (!$(id)) {
      console.error(`[initAudio] element #${id} tidak ditemukan — panel-audio aborted`);
      return;
    }
  }

  updateDurationLabel();

  // Listener sederhana, tanpa cross-call ke syncOutputExt saat input belum ada
  $('audioDuration').addEventListener('input', updateDurationLabel);
  $('audioFormat').addEventListener('change', syncOutputExt);

  // ── Browse ──────────────────────────────
  $('audioBrowse').addEventListener('click', async () => {
    try {
      const path = await browseAudio();
      if (!path) return;
      $('audioInput').value = path;
      setWorkspace(path);
      AppState.audioOriginalPath = path;
      syncOutputExt();
      try {
        const info = await probeFile(path);
        if (info && !info.error) showFileInfo('audioInfo', info);
      } catch (_) {}
    } catch (e) {
      console.error('[audioBrowse]', e);
      toast('Gagal membuka file browser', 'error');
    }
  });

  // Auto-fill dari denoise saat tab dibuka
  document.querySelector('.nav-item[data-tool="audio"]')
    ?.addEventListener('click', () => {
      if (AppState.audioDenoisedPath) {
        $('audioInput').value = AppState.audioDenoisedPath;
        syncOutputExt();
      }
    });

  // ── Process ─────────────────────────────
  $('audioProcess').addEventListener('click', async () => {
    const btn = $('audioProcess');
    try {
      const input = val('audioInput').trim();
      if (!input) { toast('Pilih file audio dulu', 'error'); return; }

      const fmt    = val('audioFormat', 'aac');
      const ext    = FORMAT_EXT[fmt] || '.m4a';
      const output = val('audioOutput').trim() || buildOutputPath(input, '._looped', ext);
      const xfade  = parseFloat(val('audioXfade', '2.0')) || 2.0;
      const dur    = parseInt(val('audioDuration', '3600')) || 3600;

      btn.disabled    = true;
      btn.textContent = '⏳ Memproses...';

      const { ok, finalData } = await consumeSSE(
        '/api/audio/loop',
        { input, output, duration: dur, format: fmt, xfade },
        'audioLog',
        'audioProgressWrap',
        'audioProgressFill',
        'audioProgressLabel'
      );

      btn.disabled    = false;
      btn.textContent = '▶ Proses Audio Loop';

      if (ok) {
        // Pakai output path dari backend (bisa beda ekstensi dari frontend)
        const finalPath = finalData?.output || output;
        AppState.audioLoopedPath = finalPath;
        toast(`✓ Audio loop selesai · ${finalData?.size || ''}`, 'success');
        document.querySelector('.nav-item[data-tool="audio"]')?.classList.add('done');
      } else {
        toast('Audio processing gagal — cek log', 'error');
      }
    } catch (e) {
      console.error('[audioProcess]', e);
      if (btn) { btn.disabled = false; btn.textContent = '▶ Proses Audio Loop'; }
      toast(`Error: ${e.message}`, 'error');
    }
  });
}
