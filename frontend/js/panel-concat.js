// ═══════════════════════════════════════════════════════════════
//  Panel: Clip Concatenator (Gabung Klip)
// ═══════════════════════════════════════════════════════════════
import { AppState, setWorkspace, buildOutputPath } from './state.js';
import { browseVideos, probeVideos } from './api.js';
import { toast, consumeSSE } from './ui.js';

export function initConcat() {
  const $ = id => document.getElementById(id);

  AppState.concatClips = AppState.concatClips || [];

  // Initialize SortableJS
  let sortableInstance = null;
  const listEl = $('concatList');
  if (listEl && window.Sortable) {
    sortableInstance = new window.Sortable(listEl, {
      handle: '.handle',
      animation: 150,
      onEnd: () => {
        const children = Array.from(listEl.children);
        if (children.length > 0 && children[0].dataset.idx !== undefined) {
          const newOrder = children.map(child => parseInt(child.dataset.idx));
          const reorderedClips = newOrder.map(idx => AppState.concatClips[idx]);
          AppState.concatClips = reorderedClips;
          renderConcatList();
          updateOutputFilename();
        }
      }
    });
  }

  // Browse videos handler
  $('concatBrowse')?.addEventListener('click', async () => {
    try {
      const paths = await browseVideos();
      if (!paths || paths.length === 0) return;

      const probed = await probeVideos(paths);
      if (probed.error) {
        toast(probed.error, 'error');
        return;
      }

      // Add probed paths to app state
      probed.paths.forEach(clip => {
        if (clip.error) {
          toast(`Gagal memuat ${clip.path}: ${clip.error}`, 'error');
        } else {
          AppState.concatClips.push(clip);
        }
      });

      renderConcatList();
      calculateTotalDuration();
      updateOutputFilename();
    } catch (err) {
      toast('Error saat memuat video: ' + err.message, 'error');
    }
  });

  // Radio toggle for transitions
  document.querySelectorAll('input[name="concatTransition"]').forEach(radio => {
    radio.addEventListener('change', () => {
      const isXfade = document.querySelector('input[name="concatTransition"]:checked')?.value === 'crossfade';
      $('concatXfadeControls')?.classList.toggle('ctrl-off', !isXfade);
      calculateTotalDuration();
    });
  });

  $('concatXfadeDuration')?.addEventListener('input', () => {
    calculateTotalDuration();
  });

  // Process concat execution
  $('concatProcess')?.addEventListener('click', async () => {
    if (!AppState.concatClips || AppState.concatClips.length < 2) {
      toast('Pilih minimal 2 klip video terlebih dahulu', 'warning');
      return;
    }

    const output = $('concatOutput').value;
    if (!output) {
      toast('Output path tidak valid', 'error');
      return;
    }

    const paths = AppState.concatClips.map(c => c.path);
    const transitionType = document.querySelector('input[name="concatTransition"]:checked')?.value || 'hard_cut';
    const transitionDuration = parseFloat($('concatXfadeDuration').value) || 1.0;

    const payload = {
      video_paths: paths,
      transition_type: transitionType,
      transition_duration: transitionDuration,
      output_path: output
    };

    $('concatProcess').disabled = true;
    $('concatDownloadBtn')?.classList.add('hidden');

    try {
      const { ok, finalData } = await consumeSSE(
        '/api/concat/render',
        payload,
        'concatLog',
        'concatProgressWrap',
        'concatProgressFill',
        'concatProgressLabel'
      );

      if (ok && finalData?.output) {
        AppState.videoProcessedPath = finalData.output;
        const mergeVideo = document.getElementById("mergeVideo");
        if (mergeVideo) {
          mergeVideo.value = finalData.output;
          mergeVideo.dispatchEvent(new Event("change"));
        }
        toast('Penggabungan klip selesai!', 'success');
        const dlBtn = $('concatDownloadBtn');
        if (dlBtn) {
          dlBtn.href = `/api/concat/download?path=${encodeURIComponent(finalData.output)}`;
          dlBtn.classList.remove('hidden');
        }
      } else {
        toast('Gagal menggabungkan klip', 'error');
      }
    } catch (err) {
      toast('Error rendering: ' + err.message, 'error');
    } finally {
      $('concatProcess').disabled = false;
    }
  });

  // Helper functions
  function renderConcatList() {
    if (!listEl) return;
    listEl.innerHTML = '';

    if (AppState.concatClips.length === 0) {
      listEl.innerHTML = `<div style="text-align:center;padding:20px;color:var(--text-faint);border:1px dashed var(--border);border-radius:var(--radius-md);">Daftar klip kosong. Silakan pilih file video.</div>`;
      $('concatTotalCount').textContent = '0';
      $('concatTotalDuration').textContent = '0s';
      return;
    }

    AppState.concatClips.forEach((clip, idx) => {
      const div = document.createElement('div');
      div.className = 'audio-layer';
      div.style.cssText = 'grid-template-columns: 24px 20px 1fr 70px 70px 32px 28px; gap: 8px; align-items: center; margin-bottom: 8px;';
      div.dataset.idx = idx;

      div.innerHTML = `
        <span class="handle" style="cursor: grab; color: var(--text-faint); font-weight: bold; text-align: center; user-select: none;">⠿</span>
        <span class="merge-num" style="width: auto; height: auto; border: none; background: transparent; font-size: 13px; font-weight: 600; color: var(--text-muted);">${idx + 1}</span>
        <span style="font-family: var(--font-mono); font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--text);" title="${clip.path}">${clip.filename}</span>
        <span style="font-size: 11px; color: var(--text-muted); text-align: right;">${clip.duration_str}</span>
        <span style="font-size: 11px; color: var(--text-muted); text-align: right;">${clip.size_str}</span>
        <div style="display: flex; flex-direction: column; gap: 2px; align-items: center; justify-content: center;">
          <button class="btn-btn-up" style="background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 9px; line-height: 1; padding: 2px 4px;" title="Pindahkan ke atas">▲</button>
          <button class="btn-btn-down" style="background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 9px; line-height: 1; padding: 2px 4px;" title="Pindahkan ke bawah">▼</button>
        </div>
        <button class="btn-remove" style="width: 24px; height: 24px; font-size: 14px; margin-left: auto;" title="Hapus klip">×</button>
      `;

      // Up/Down button events
      div.querySelector('.btn-btn-up').addEventListener('click', (e) => {
        e.stopPropagation();
        if (idx > 0) {
          const temp = AppState.concatClips[idx];
          AppState.concatClips[idx] = AppState.concatClips[idx - 1];
          AppState.concatClips[idx - 1] = temp;
          renderConcatList();
          calculateTotalDuration();
          updateOutputFilename();
        }
      });

      div.querySelector('.btn-btn-down').addEventListener('click', (e) => {
        e.stopPropagation();
        if (idx < AppState.concatClips.length - 1) {
          const temp = AppState.concatClips[idx];
          AppState.concatClips[idx] = AppState.concatClips[idx + 1];
          AppState.concatClips[idx + 1] = temp;
          renderConcatList();
          calculateTotalDuration();
          updateOutputFilename();
        }
      });

      // Remove button event
      div.querySelector('.btn-remove').addEventListener('click', (e) => {
        e.stopPropagation();
        AppState.concatClips.splice(idx, 1);
        renderConcatList();
        calculateTotalDuration();
        updateOutputFilename();
      });

      listEl.appendChild(div);
    });

    $('concatTotalCount').textContent = AppState.concatClips.length;
  }

  function formatDuration(sec) {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    if (h > 0) {
      return `${h}j ${m.toString().padStart(2, '0')}m ${Math.floor(s).toString().padStart(2, '0')}s`;
    } else if (m > 0) {
      return `${m}m ${Math.floor(s).toString().padStart(2, '0')}s`;
    } else {
      return `${s.toFixed(1)}s`;
    }
  }

  function calculateTotalDuration() {
    if (!AppState.concatClips || AppState.concatClips.length === 0) {
      $('concatTotalDuration').textContent = '0s';
      return;
    }

    const durations = AppState.concatClips.map(c => c.duration);
    const isXfade = document.querySelector('input[name="concatTransition"]:checked')?.value === 'crossfade';
    const xfadeDur = parseFloat($('concatXfadeDuration').value) || 1.0;

    let total = 0;
    if (isXfade) {
      const N = AppState.concatClips.length;
      total = durations.reduce((sum, d) => sum + d, 0) - (N - 1) * xfadeDur;
    } else {
      total = durations.reduce((sum, d) => sum + d, 0);
    }

    $('concatTotalDuration').textContent = formatDuration(Math.max(0, total));
  }

  function updateOutputFilename() {
    if (!AppState.concatClips || AppState.concatClips.length === 0) {
      $('concatOutput').value = '';
      return;
    }

    const firstPath = AppState.concatClips[0].path;
    setWorkspace(firstPath);

    const now = new Date();
    const YYYY = now.getFullYear();
    const MM = (now.getMonth() + 1).toString().padStart(2, '0');
    const DD = now.getDate().toString().padStart(2, '0');
    const hh = now.getHours().toString().padStart(2, '0');
    const mm = now.getMinutes().toString().padStart(2, '0');
    const ss = now.getSeconds().toString().padStart(2, '0');

    const suffix = `_gabung_${YYYY}${MM}${DD}_${hh}${mm}${ss}`;
    $('concatOutput').value = buildOutputPath(firstPath, suffix, '.mp4');
  }
}
