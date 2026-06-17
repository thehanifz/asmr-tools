// ═══════════════════════════════════════════════
//  Panel: Crop & Upscale  v1.0.0
//  Standalone crop/upscale tanpa loop
// ═══════════════════════════════════════════════
import { AppState, setWorkspace, buildOutputPath } from './state.js';
import { browseVideo, probeFile }                  from './api.js';
import { toast, showFileInfo, consumeSSE }         from './ui.js';

export function initCrop() {
  const $ = id => document.getElementById(id);

  // ── Browse input ──────────────────────────────────────────
  $('cropBrowse').addEventListener('click', async () => {
    const path = await browseVideo();
    if (!path) return;
    $('cropInput').value = path;
    setWorkspace(path);
    AppState.cropOriginalPath = path;
    $('cropOutput').value = buildOutputPath(path, '._cropped', '.mp4');
    const info = await probeFile(path);
    if (info.error) { toast(info.error, 'error'); return; }
    showFileInfo('cropInfo', info);
  });

  // ── Update summary ────────────────────────────────────────
  function updateSummary() {
    const t = $('cropPanelTop').value    || '0';
    const b = $('cropPanelBottom').value || '0';
    const l = $('cropPanelLeft').value   || '0';
    const r = $('cropPanelRight').value  || '0';
    const res = $('cropUpscaleRes').value;
    const resLabel = res ? res.replace(':', '×') : '—';
    const el = $('cropPanelSummary');
    if (el) el.textContent = `T:${t} B:${b} L:${l} R:${r} | ${resLabel}`;
  }

  ['cropPanelTop','cropPanelBottom','cropPanelLeft','cropPanelRight','cropUpscaleRes']
    .forEach(id => $(id)?.addEventListener('input', updateSummary));
  updateSummary();

  // ── Process ───────────────────────────────────────────────
  $('cropProcess').addEventListener('click', async () => {
    const input = $('cropInput').value;
    if (!input) { toast('Pilih file video dulu', 'error'); return; }

    const cropTop    = parseInt($('cropPanelTop').value)    || 0;
    const cropBottom = parseInt($('cropPanelBottom').value) || 0;
    const cropLeft   = parseInt($('cropPanelLeft').value)   || 0;
    const cropRight  = parseInt($('cropPanelRight').value)  || 0;
    const upscale    = $('cropUpscaleRes').value;
    const crf        = parseInt($('cropCrf').value)         || 23;

    if (!cropTop && !cropBottom && !cropLeft && !cropRight && !upscale) {
      toast('Set minimal satu nilai crop atau pilih resolusi upscale', 'error');
      return;
    }

    const output = $('cropOutput').value || buildOutputPath(input, '._cropped', '.mp4');

    const payload = {
      input,
      output,
      crop_top:    cropTop,
      crop_bottom: cropBottom,
      crop_left:   cropLeft,
      crop_right:  cropRight,
      upscale,
      crf,
    };

    $('cropProcess').disabled = true;
    const { ok, finalData } = await consumeSSE(
      '/api/video/crop', payload,
      'cropLog', 'cropProgressWrap', 'cropProgressFill', 'cropProgressLabel'
    );
    $('cropProcess').disabled = false;

    if (ok && finalData) {
      // Simpan output crop ke AppState agar bisa di-pick oleh panel Video dan Merge
      const finalOut = finalData.output || output;
      AppState.cropOutputPath = finalOut;
      AppState.videoProcessedPath = finalOut;
      const mergeVideo = document.getElementById("mergeVideo");
      if (mergeVideo) {
        mergeVideo.value = finalOut;
        mergeVideo.dispatchEvent(new Event("change"));
      }
      toast(`Crop selesai · ${finalData.final_size || ''}`, 'success');
      document.querySelector('.nav-item[data-tool="crop"]')?.classList.add('done');
    } else {
      toast('Crop gagal', 'error');
    }
  });

  // ── Tombol "Lanjut ke Video Loop" ─────────────────────────
  $('cropToVideoBtn')?.addEventListener('click', () => {
    if (!AppState.cropOutputPath) {
      toast('Proses crop dulu sebelum lanjut ke Video Loop', 'error');
      return;
    }
    // Isi input Video panel dengan output crop
    const videoInput = document.getElementById('videoInput');
    if (videoInput) videoInput.value = AppState.cropOutputPath;
    // Trigger probe agar info & workspace ter-update
    document.getElementById('videoBrowse')?.dispatchEvent(new CustomEvent('use-path', { detail: AppState.cropOutputPath }));
    // Pindah ke tab Video
    document.querySelector('.nav-item[data-tool="video"]')?.click();
  });
}
