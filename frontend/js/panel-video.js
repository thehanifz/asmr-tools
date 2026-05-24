// ═══════════════════════════════════════════════
//  Panel: Video Loop  v3.0.0
//  Loop + XFade + Fade In/Out (tanpa crop)
// ═══════════════════════════════════════════════
import { AppState, setWorkspace, buildOutputPath } from './state.js';
import { browseVideo, probeFile }                  from './api.js';
import { toast, showFileInfo, consumeSSE }         from './ui.js';

export function initVideo() {
  const $ = id => document.getElementById(id);

  // ── helpers toggle ctrl-off ────────────────────────────────
  function syncCtrl(checkboxId, wrapId) {
    const cb   = $(checkboxId);
    const wrap = $(wrapId);
    if (!cb || !wrap) return;
    const update = () => wrap.classList.toggle('ctrl-off', !cb.checked);
    cb.addEventListener('change', update);
    update();
  }

  syncCtrl('videoFadeInEnabled',  'fadeInControls');
  syncCtrl('videoFadeOutEnabled', 'fadeOutControls');
  syncCtrl('videoXfadeEnabled',   'xfadeControls');

  // ── collapsibles ──────────────────────────────────────────
  function initCollapsible(toggleId, bodyId, defaultOpen = false) {
    const toggle = $(toggleId);
    const body   = $(bodyId);
    if (!toggle || !body) return;
    if (defaultOpen) {
      body.classList.add('open');
      toggle.setAttribute('aria-expanded', 'true');
    }
    toggle.addEventListener('click', () => {
      const isOpen = body.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(isOpen));
    });
  }

  initCollapsible('toggleFade',  'fadeBody',  false);
  initCollapsible('toggleXfade', 'xfadeBody', false);

  function updateFadeSummary() {
    const fi = $('videoFadeInEnabled').checked;
    const fo = $('videoFadeOutEnabled').checked;
    if (!$('fadeSummary')) return;
    if (!fi && !fo) { $('fadeSummary').textContent = 'OFF'; return; }
    const parts = [];
    if (fi) parts.push(`In:${$('videoFadeInDuration').value}s`);
    if (fo) parts.push(`Out:${$('videoFadeOutDuration').value}s`);
    $('fadeSummary').textContent = parts.join(' ');
  }
  function updateXfadeSummary() {
    const en = $('videoXfadeEnabled').checked;
    if (!$('xfadeSummary')) return;
    $('xfadeSummary').textContent = en
      ? `${$('videoXfadeDuration').value}s / ${$('videoXfadeType').value}`
      : 'OFF';
  }

  ['videoFadeInEnabled','videoFadeOutEnabled','videoFadeInDuration','videoFadeOutDuration']
    .forEach(id => $(id)?.addEventListener('change', updateFadeSummary));
  ['videoXfadeEnabled','videoXfadeDuration','videoXfadeType']
    .forEach(id => $(id)?.addEventListener('change', updateXfadeSummary));

  updateFadeSummary();
  updateXfadeSummary();

  // ── browse ────────────────────────────────────────────────
  $('videoBrowse').addEventListener('click', async () => {
    const path = await browseVideo();
    if (!path) return;
    _loadVideoPath(path);
  });

  // Custom event dari panel Crop "Lanjut ke Video Loop"
  $('videoBrowse').addEventListener('use-path', async (e) => {
    if (e.detail) _loadVideoPath(e.detail);
  });

  async function _loadVideoPath(path) {
    $('videoInput').value = path;
    setWorkspace(path);
    AppState.videoOriginalPath = path;
    $('videoOutput').value = buildOutputPath(path, '._looped', '.mp4');
    const info = await probeFile(path);
    if (info.error) { toast(info.error, 'error'); return; }
    showFileInfo('videoInfo', info);
    AppState.videoDuration = info.duration || 8;
  }

  $('videoKeepAudio').addEventListener('change', e => {
    AppState.videoKeepAudio = e.target.checked;
  });

  // ── process ───────────────────────────────────────────────
  $('videoProcess').addEventListener('click', async () => {
    const input = $('videoInput').value;
    if (!input) { toast('Pilih file video dulu', 'error'); return; }

    const output = $('videoOutput').value || buildOutputPath(input, '._looped', '.mp4');

    const payload = {
      input,
      output,
      duration:       parseInt($('videoDuration').value) || 3600,
      video_duration: AppState.videoDuration,
      keep_audio:     AppState.videoKeepAudio,

      fade_in_enabled:   $('videoFadeInEnabled').checked,
      fade_in_duration:  parseFloat($('videoFadeInDuration').value)  || 3.0,
      fade_out_enabled:  $('videoFadeOutEnabled').checked,
      fade_out_duration: parseFloat($('videoFadeOutDuration').value) || 3.0,

      xfade_enabled:  $('videoXfadeEnabled').checked,
      xfade_duration: parseFloat($('videoXfadeDuration').value) || 1.0,
    };

    $('videoProcess').disabled = true;
    const { ok, finalData } = await consumeSSE(
      '/api/video/pipeline', payload,
      'videoLog', 'videoProgressWrap', 'videoProgressFill', 'videoProgressLabel'
    );
    $('videoProcess').disabled = false;

    if (ok && finalData) {
      AppState.videoProcessedPath = finalData.output || output;
      toast(`Video selesai · ${finalData.final_size || ''}`, 'success');
      document.querySelector('.nav-item[data-tool="video"]')?.classList.add('done');
    } else {
      toast('Video processing gagal', 'error');
    }
  });
}
