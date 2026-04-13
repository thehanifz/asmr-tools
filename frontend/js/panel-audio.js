// ═══════════════════════════════════════════════
//  Panel: Audio Loop
// ═══════════════════════════════════════════════
import { AppState, setWorkspace, buildOutputPath } from './state.js';
import { browseAudio, probeFile }                  from './api.js';
import { toast, showFileInfo, consumeSSE, logAppend, logClear } from './ui.js';

const FORMAT_EXT = { mp3: '.mp3', aac: '.m4a', flac: '.flac', wav: '.wav' };

function updateDurationLabel() {
  try {
    const sec = parseInt(document.getElementById('audioDuration').value) || 0;
    const h   = Math.floor(sec / 3600);
    const m   = Math.floor((sec % 3600) / 60);
    const label = h > 0 ? `= ${h} jam${m > 0 ? ' ' + m + ' mnt' : ''}` : `= ${m} menit`;
    const el = document.getElementById('audioDurationLabel');
    if (el) el.textContent = label;
  } catch (e) { console.warn('updateDurationLabel', e); }
}

function syncOutputExt() {
  try {
    const input = document.getElementById('audioInput').value;
    const fmt   = document.getElementById('audioFormat').value;
    const outEl = document.getElementById('audioOutput');
    if (!outEl) return;
    if (input) {
      outEl.value = buildOutputPath(input, '._looped', FORMAT_EXT[fmt] || '.m4a');
    }
  } catch (e) { console.warn('syncOutputExt', e); }
}

export function initAudio() {
  const $ = id => document.getElementById(id);

  // Pastikan semua elemen ada
  const requiredIds = ['audioBrowse', 'audioProcess', 'audioDuration', 'audioFormat', 'audioXfade', 'audioInput', 'audioOutput'];
  for (const id of requiredIds) {
    if (!$(id)) { console.error(`initAudio: element #${id} tidak ditemukan`); return; }
  }

  // Init label
  updateDurationLabel();
  $('audioDuration').addEventListener('input', updateDurationLabel);
  $('audioFormat').addEventListener('change', syncOutputExt);

  // ── Browse ──────────────────────────────────
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
      console.error('audioBrowse error:', e);
      toast('Gagal membuka file browser', 'error');
    }
  });

  // Auto-fill dari denoise result
  document.querySelector('.nav-item[data-tool="audio"]')?.addEventListener('click', () => {
    try {
      if (AppState.audioDenoisedPath && !$('audioInput').value) {
        $('audioInput').value = AppState.audioDenoisedPath;
        syncOutputExt();
      }
    } catch (_) {}
  });

  // ── Process ─────────────────────────────────
  $('audioProcess').addEventListener('click', async () => {
    try {
      console.log('[Audio Loop] Button clicked');
      
      const input = $('audioInput').value.trim();
      if (!input) { toast('Pilih file audio dulu', 'error'); return; }
      console.log('[Audio Loop] Input:', input);

      const fmt    = $('audioFormat').value;
      const ext    = FORMAT_EXT[fmt] || '.m4a';
      const output = $('audioOutput').value.trim() || buildOutputPath(input, '._looped', ext);
      const xfade  = parseFloat($('audioXfade').value) || 2.0;
      const dur    = parseInt($('audioDuration').value) || 3600;

      console.log('[Audio Loop] Settings:', { fmt, output, xfade, dur });

      const payload = {
        input,
        output,
        duration: dur,
        format:   fmt,
        xfade,
      };

      $('audioProcess').disabled = true;
      $('audioProcess').textContent = '⏳ Memproses...';

      console.log('[Audio Loop] Calling API:', '/api/audio/loop', payload);

      const { ok, finalData } = await consumeSSE(
        '/api/audio/loop', payload,
        'audioLog', 'audioProgressWrap', 'audioProgressFill', 'audioProgressLabel'
      );

      console.log('[Audio Loop] Response:', { ok, finalData });

      $('audioProcess').disabled = false;
      $('audioProcess').textContent = '▶ Proses Audio Loop';

      if (ok) {
        AppState.audioLoopedPath = output;
        toast(`✓ Audio selesai${finalData?.size ? ' · ' + finalData.size : ''}`, 'success');
        document.querySelector('.nav-item[data-tool="audio"]')?.classList.add('done');
      } else {
        toast('Audio processing gagal — cek log', 'error');
      }
    } catch (e) {
      console.error('[Audio Loop] Error:', e);
      $('audioProcess').disabled = false;
      $('audioProcess').textContent = '▶ Proses Audio Loop';
      toast(`Error: ${e.message}`, 'error');
    }
  });
}
