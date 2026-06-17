// ═══════════════════════════════════════════════════════════════
//  Panel: Loop B+A (Video Segment Swap)
// ═══════════════════════════════════════════════════════════════
import { AppState, setWorkspace, buildOutputPath } from './state.js';
import { browseVideo, probeFile } from './api.js';
import { toast, showFileInfo, consumeSSE } from './ui.js';

export function initLoopBA() {
  const $ = id => document.getElementById(id);

  // Transition toggle handler
  document.querySelectorAll('input[name="loopBaTransition"]').forEach(radio => {
    radio.addEventListener('change', () => {
      const isXfade = document.querySelector('input[name="loopBaTransition"]:checked')?.value === 'crossfade';
      $('loopBaXfadeControls')?.classList.toggle('ctrl-off', !isXfade);
    });
  });

  // Browse video click event
  $('loopBaBrowse')?.addEventListener('click', async () => {
    try {
      const path = await browseVideo();
      if (!path) return;
      
      $('loopBaInput').value = path;
      setWorkspace(path);

      const info = await probeFile(path);
      if (info.error) {
        toast(info.error, 'error');
        return;
      }

      showFileInfo('loopBaInfo', info);

      // Store video properties
      AppState.loopBaOriginalPath = path;
      AppState.loopBaDuration = info.duration || 0;

      // Update segment visualization
      if (AppState.loopBaDuration > 0) {
        const total = AppState.loopBaDuration;
        const mid = total / 2;

        $('loopBaSegAInfo').textContent = `Segmen A: ${formatTime(0)} s/d ${formatTime(mid)}`;
        $('loopBaSegBInfo').textContent = `Segmen B: ${formatTime(mid)} s/d ${formatTime(total)}`;
        $('loopBaSegmentsGroup')?.classList.remove('hidden');
      } else {
        $('loopBaSegmentsGroup')?.classList.add('hidden');
      }

      // Generate output path automatically
      const now = new Date();
      const YYYY = now.getFullYear();
      const MM = (now.getMonth() + 1).toString().padStart(2, '0');
      const DD = now.getDate().toString().padStart(2, '0');
      const hh = now.getHours().toString().padStart(2, '0');
      const mm = now.getMinutes().toString().padStart(2, '0');
      const ss = now.getSeconds().toString().padStart(2, '0');
      
      const suffix = `_loop_ba_${YYYY}${MM}${DD}_${hh}${mm}${ss}`;
      $('loopBaOutput').value = buildOutputPath(path, suffix, '.mp4');
      $('loopBaDownloadBtn')?.classList.add('hidden');

    } catch (err) {
      toast('Error loading video: ' + err.message, 'error');
    }
  });

  // Process rendering click event
  $('loopBaProcess')?.addEventListener('click', async () => {
    const input = $('loopBaInput').value;
    if (!input) {
      toast('Pilih file video terlebih dahulu', 'warning');
      return;
    }

    const output = $('loopBaOutput').value;
    if (!output) {
      toast('Output path tidak valid', 'error');
      return;
    }

    const isXfade = document.querySelector('input[name="loopBaTransition"]:checked')?.value === 'crossfade';
    const xfadeDuration = parseFloat($('loopBaXfadeDuration').value) || 1.0;

    // Validate crossfade duration against half duration
    if (isXfade && AppState.loopBaDuration > 0) {
      const bDuration = AppState.loopBaDuration / 2;
      if (xfadeDuration > bDuration) {
        toast(`Durasi crossfade (${xfadeDuration}s) tidak boleh melebihi durasi paruh kedua (${bDuration.toFixed(2)}s)`, 'error');
        return;
      }
    }

    const payload = {
      input_path: input,
      transition_type: isXfade ? 'crossfade' : 'hard_cut',
      transition_duration: xfadeDuration,
      output_path: output
    };

    $('loopBaProcess').disabled = true;
    $('loopBaDownloadBtn')?.classList.add('hidden');

    try {
      const { ok, finalData } = await consumeSSE(
        '/api/loop-ba/render',
        payload,
        'loopBaLog',
        'loopBaProgressWrap',
        'loopBaProgressFill',
        'loopBaProgressLabel'
      );

      if (ok && finalData?.output) {
        AppState.videoProcessedPath = finalData.output;
        const mergeVideo = document.getElementById("mergeVideo");
        if (mergeVideo) {
          mergeVideo.value = finalData.output;
          mergeVideo.dispatchEvent(new Event("change"));
        }
        toast('Loop B+A render selesai!', 'success');
        const dlBtn = $('loopBaDownloadBtn');
        if (dlBtn) {
          dlBtn.href = `/api/loop-ba/download?path=${encodeURIComponent(finalData.output)}`;
          dlBtn.classList.remove('hidden');
        }
      } else {
        toast('Gagal melakukan render Loop B+A', 'error');
      }
    } catch (err) {
      toast('Error rendering: ' + err.message, 'error');
    } finally {
      $('loopBaProcess').disabled = false;
    }
  });

  // Helper: format seconds to HH:MM:SS.ms
  function formatTime(sec) {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = Math.floor(sec % 60);
    const ms = Math.floor((sec % 1) * 100);
    
    const h_str = h.toString().padStart(2, '0');
    const m_str = m.toString().padStart(2, '0');
    const s_str = s.toString().padStart(2, '0');
    const ms_str = ms.toString().padStart(2, '0');
    
    return `${h_str}:${m_str}:${s_str}.${ms_str}`;
  }
}
