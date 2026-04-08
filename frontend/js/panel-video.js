// ═══════════════════════════════════════════════
//  Panel: Video Pipeline  v2.4.0
//  fade in/out + xfade seamless loop
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

  // ── browse ────────────────────────────────────────────────
  $('videoBrowse').addEventListener('click', async () => {
    const path = await browseVideo();
    if (!path) return;
    $('videoInput').value = path;
    setWorkspace(path);
    AppState.videoOriginalPath = path;
    $('videoOutput').value = buildOutputPath(path, '._processed', '.mp4');
    const info = await probeFile(path);
    if (info.error) { toast(info.error, 'error'); return; }
    showFileInfo('videoInfo', info);
    AppState.videoDuration = info.duration || 8;
  });

  $('videoKeepAudio').addEventListener('change', e => {
    AppState.videoKeepAudio = e.target.checked;
  });

  // ── process ───────────────────────────────────────────────
  $('videoProcess').addEventListener('click', async () => {
    const input = $('videoInput').value;
    if (!input) { toast('Pilih file video dulu', 'error'); return; }

    const output = $('videoOutput').value || buildOutputPath(input, '._processed', '.mp4');

    const payload = {
      input,
      output,
      crop_top:    parseInt($('cropTop').value)    || 0,
      crop_bottom: parseInt($('cropBottom').value) || 0,
      crop_left:   parseInt($('cropLeft').value)   || 0,
      crop_right:  parseInt($('cropRight').value)  || 0,
      upscale:     $('upscaleRes').value,
      duration:    parseInt($('videoDuration').value) || 3600,
      video_duration: AppState.videoDuration,
      keep_audio:  AppState.videoKeepAudio,

      // fade in/out
      fade_in_enabled:   $('videoFadeInEnabled').checked,
      fade_in_duration:  parseFloat($('videoFadeInDuration').value)  || 3.0,
      fade_out_enabled:  $('videoFadeOutEnabled').checked,
      fade_out_duration: parseFloat($('videoFadeOutDuration').value) || 3.0,

      // xfade
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
