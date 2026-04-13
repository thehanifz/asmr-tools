// ═══════════════════════════════════════════════
//  Panel: Audio Loop
// ═══════════════════════════════════════════════
import { AppState, setWorkspace, buildOutputPath } from './state.js';
import { browseAudio, probeFile }                  from './api.js';
import { toast, showFileInfo, consumeSSE }         from './ui.js';

// Format → extension map
const FORMAT_EXT = { mp3: '.mp3', aac: '.m4a', flac: '.flac', wav: '.wav' };

// Update label durasi (jam / menit)
function updateDurationLabel() {
  const sec = parseInt(document.getElementById('audioDuration').value) || 0;
  const h   = Math.floor(sec / 3600);
  const m   = Math.floor((sec % 3600) / 60);
  const label = h > 0 ? `= ${h} jam ${m > 0 ? m + ' mnt' : ''}` : `= ${m} menit`;
  const el = document.getElementById('audioDurationLabel');
  if (el) el.textContent = label;
}

// Sync ekstensi output saat format berubah
function syncOutputExt() {
  const input  = document.getElementById('audioInput').value;
  const fmt    = document.getElementById('audioFormat').value;
  const outEl  = document.getElementById('audioOutput');
  if (input && outEl.value) {
    const ext  = FORMAT_EXT[fmt] || '.m4a';
    outEl.value = buildOutputPath(input, '._looped', ext);
  }
}

export function initAudio() {
  const $ = id => document.getElementById(id);

  // Init label
  updateDurationLabel();
  $('audioDuration').addEventListener('input', updateDurationLabel);
  $('audioFormat').addEventListener('change', syncOutputExt);

  // ── Browse ──────────────────────────────────
  $('audioBrowse').addEventListener('click', async () => {
    const path = await browseAudio();
    if (!path) return;
    $('audioInput').value = path;
    setWorkspace(path);
    AppState.audioOriginalPath = path;
    const fmt = $('audioFormat').value;
    $('audioOutput').value = buildOutputPath(path, '._looped', FORMAT_EXT[fmt] || '.m4a');
    const info = await probeFile(path);
    if (!info.error) showFileInfo('audioInfo', info);
    updateDurationLabel();
  });

  // Auto-fill dari denoise result
  document.querySelector('.nav-item[data-tool="audio"]')?.addEventListener('click', () => {
    if (AppState.audioDenoisedPath && !$('audioInput').value) {
      const fmt = $('audioFormat').value;
      $('audioInput').value  = AppState.audioDenoisedPath;
      $('audioOutput').value = buildOutputPath(AppState.audioDenoisedPath, '._looped', FORMAT_EXT[fmt] || '.m4a');
    }
  });

  // ── Process ─────────────────────────────────
  $('audioProcess').addEventListener('click', async () => {
    const input = $('audioInput').value;
    if (!input) { toast('Pilih file audio dulu', 'error'); return; }

    const fmt    = $('audioFormat').value;
    const ext    = FORMAT_EXT[fmt] || '.m4a';
    const output = $('audioOutput').value || buildOutputPath(input, '._looped', ext);

    const payload = {
      input,
      output,
      duration:    parseInt($('audioDuration').value) || 3600,
      format:      fmt,
      xfade:       parseFloat($('audioXfade').value) || 2.0,
    };

    $('audioProcess').disabled = true;
    const { ok, finalData } = await consumeSSE(
      '/api/audio/loop', payload,
      'audioLog', 'audioProgressWrap', 'audioProgressFill', 'audioProgressLabel'
    );
    $('audioProcess').disabled = false;

    if (ok) {
      AppState.audioLoopedPath = output;
      toast(`Audio selesai · ${finalData?.size || ''}`, 'success');
      document.querySelector('.nav-item[data-tool="audio"]')?.classList.add('done');
    } else {
      toast('Audio processing gagal', 'error');
    }
  });
}
