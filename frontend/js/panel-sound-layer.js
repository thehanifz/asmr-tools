// ═══════════════════════════════════════════════════════════════
//  Panel: Sound Layer — Per-Sound Smart Density
// ═══════════════════════════════════════════════════════════════
import { AppState, setWorkspace } from './state.js';
import { browseAudio, probeFile, previewSoundLayer } from './api.js';
import { toast, logClear, logAppend, consumeSSE } from './ui.js';

function $(id) { return document.getElementById(id); }

// ── Density & ClipSize maps ──────────────────────────────────
const DENSITY_SPACING = { sparse: 8, normal: 4, dense: 2, vdense: 1.2 };
const CLIP_RANGE = {
  short:  { min: 3,  max: 8  },
  medium: { min: 8,  max: 20 },
  long:   { min: 20, max: 45 },
};

function calcOccurrences(windowSec, density, clipSize) {
  const range = CLIP_RANGE[clipSize] || CLIP_RANGE.medium;
  const avg = (range.min + range.max) / 2;
  const spacing = avg * (DENSITY_SPACING[density] || 4);
  return Math.max(1, Math.floor(windowSec / spacing));
}

// ── Per-Sound Item Builder ───────────────────────────────────
function buildSoundItem(sound, idx, onRemove) {
  const div = document.createElement('div');
  div.className = 'opt-sound-item';
  div.dataset.idx = idx;

  const name = sound.path.split(/[\/\\]/).pop();

  div.innerHTML = `
    <div class="opt-sound-header">
      <button class="opt-expand-btn" title="Expand/Collapse">
        <svg class="opt-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
      </button>
      <span class="opt-sound-name" title="${sound.path}">🎵 ${name}</span>
      <span class="opt-sound-dur">${sound.duration > 0 ? sound.duration.toFixed(1) + 's' : ''}</span>
      <span class="opt-sound-est" id="optEst_${idx}"></span>
      <button class="btn btn-ghost opt-remove-btn" title="Hapus" style="color:var(--danger);padding:2px 6px;margin-left:4px;">×</button>
    </div>
    <div class="opt-sound-body collapsed">
      <!-- Volume -->
      <div class="opt-row">
        <label class="opt-label">Volume</label>
        <input type="range" class="slider opt-volume" min="0" max="100" value="${sound.volume}">
        <span class="opt-vol-val">${sound.volume}%</span>
      </div>
      <!-- Fade -->
      <div class="opt-row">
        <label class="opt-label">Fade In</label>
        <input type="number" class="input opt-fadein" value="${sound.fade_in}" min="0.1" max="10" step="0.1" style="width:70px;">
        <label class="opt-label" style="margin-left:12px;">Fade Out</label>
        <input type="number" class="input opt-fadeout" value="${sound.fade_out}" min="0.1" max="10" step="0.1" style="width:70px;">
        <span class="opt-unit">detik</span>
      </div>
      <!-- Frekuensi -->
      <div class="opt-row">
        <label class="opt-label">Frekuensi</label>
        <div class="opt-radio-group">
          <label class="opt-radio-lbl"><input type="radio" name="density_${idx}" value="sparse" ${sound.density==='sparse'?'checked':''}> Jarang</label>
          <label class="opt-radio-lbl"><input type="radio" name="density_${idx}" value="normal" ${sound.density==='normal'?'checked':''}> Normal</label>
          <label class="opt-radio-lbl"><input type="radio" name="density_${idx}" value="dense" ${sound.density==='dense'?'checked':''}> Padat</label>
          <label class="opt-radio-lbl"><input type="radio" name="density_${idx}" value="vdense" ${sound.density==='vdense'?'checked':''}> Sangat Padat</label>
        </div>
      </div>
      <!-- Ukuran Clip -->
      <div class="opt-row">
        <label class="opt-label">Ukuran Clip</label>
        <div class="opt-radio-group">
          <label class="opt-radio-lbl"><input type="radio" name="clip_${idx}" value="short" ${sound.clip_size==='short'?'checked':''}> Pendek (3-8s)</label>
          <label class="opt-radio-lbl"><input type="radio" name="clip_${idx}" value="medium" ${sound.clip_size==='medium'?'checked':''}> Sedang (8-20s)</label>
          <label class="opt-radio-lbl"><input type="radio" name="clip_${idx}" value="long" ${sound.clip_size==='long'?'checked':''}> Panjang (20-45s)</label>
        </div>
      </div>
      <!-- Window -->
      <div class="opt-row">
        <label class="opt-label">Window</label>
        <input type="number" class="input opt-wstart" value="${sound.window_start}" min="0" max="100" step="5" style="width:64px;"> %
        <span style="margin:0 6px;opacity:.5;">s/d</span>
        <input type="number" class="input opt-wend" value="${sound.window_end}" min="0" max="100" step="5" style="width:64px;"> %
      </div>
    </div>
  `;

  // Expand / Collapse
  const header  = div.querySelector('.opt-sound-header');
  const body    = div.querySelector('.opt-sound-body');
  const chevron = div.querySelector('.opt-chevron');
  header.addEventListener('click', (e) => {
    if (e.target.closest('.opt-remove-btn')) return;
    const collapsed = body.classList.toggle('collapsed');
    chevron.style.transform = collapsed ? '' : 'rotate(180deg)';
  });

  // Remove
  div.querySelector('.opt-remove-btn').addEventListener('click', (e) => {
    e.stopPropagation();
    onRemove(parseInt(div.dataset.idx));
  });

  // Sync helpers
  function getState() {
    const density   = div.querySelector(`input[name="density_${idx}"]:checked`)?.value || 'normal';
    const clip_size = div.querySelector(`input[name="clip_${idx}"]:checked`)?.value || 'medium';
    const wStart    = parseFloat(div.querySelector('.opt-wstart').value) || 0;
    const wEnd      = parseFloat(div.querySelector('.opt-wend').value)   || 100;
    return { density, clip_size, wStart, wEnd };
  }

  function updateEst() {
    const targetDur = parseFloat($('soundLayerTargetDuration')?.value) || 3600;
    const { density, clip_size, wStart, wEnd } = getState();
    const windowSec = ((wEnd - wStart) / 100) * targetDur;
    const occ = calcOccurrences(windowSec, density, clip_size);
    const est = $(`optEst_${idx}`);
    if (est) est.textContent = `~${occ}x`;
  }

  function syncToState() {
    const s = AppState.optionalSounds[parseInt(div.dataset.idx)];
    if (!s) return;
    const { density, clip_size, wStart, wEnd } = getState();
    s.density       = density;
    s.clip_size     = clip_size;
    s.window_start  = wStart;
    s.window_end    = wEnd;
    s.volume    = parseInt(div.querySelector('.opt-volume').value);
    s.fade_in   = parseFloat(div.querySelector('.opt-fadein').value);
    s.fade_out  = parseFloat(div.querySelector('.opt-fadeout').value);
    updateEst();
  }

  // Volume display
  const volSlider = div.querySelector('.opt-volume');
  const volVal    = div.querySelector('.opt-vol-val');
  volSlider.addEventListener('input', () => {
    volVal.textContent = volSlider.value + '%';
    syncToState();
  });

  div.querySelectorAll('.opt-fadein, .opt-fadeout, .opt-wstart, .opt-wend').forEach(el => {
    el.addEventListener('input', syncToState);
  });
  div.querySelectorAll(`input[name^="density_"], input[name^="clip_"]`).forEach(el => {
    el.addEventListener('change', syncToState);
  });

  updateEst();
  return div;
}

// ── Render optional list ─────────────────────────────────────
function renderOptionalList() {
  const list = $('optSoundList');
  if (!list) return;
  list.innerHTML = '';
  AppState.optionalSounds.forEach((s, idx) => {
    const el = buildSoundItem(s, idx, (i) => {
      AppState.optionalSounds.splice(i, 1);
      renderOptionalList();
    });
    list.appendChild(el);
  });
}

// ── Main init ────────────────────────────────────────────────
export function initSoundLayer() {

  // ── Main sounds ──────────────────────────────────────────────
  AppState.mainSounds = AppState.mainSounds || [];

  function renderMainSoundsList() {
    const list = $('soundLayerMainList');
    if (!list) return;
    list.innerHTML = '';
    const addBtn = $('soundLayerAddMainBtn');
    if (addBtn) addBtn.disabled = AppState.mainSounds.length >= 3;

    AppState.mainSounds.forEach((snd, idx) => {
      const div = document.createElement('div');
      div.className = 'file-row';
      div.style.cssText = 'flex-direction:column;align-items:stretch;gap:8px;padding:10px;background:var(--bg-hover);border-radius:6px;';
      div.innerHTML = `
        <div style="display:flex;gap:8px;align-items:center;">
          <input type="text" class="file-input" value="${snd.path}" readonly style="flex:1;">
          <button class="btn btn-ghost" style="color:var(--danger);" data-idx="${idx}">Hapus</button>
        </div>
        <div style="display:flex;gap:12px;align-items:center;">
          <label style="font-size:12px;min-width:50px;">Volume</label>
          <input type="range" class="slider vol-slider" data-idx="${idx}" min="0" max="100" value="${snd.volume}" style="flex:1;">
          <span style="font-family:var(--font-mono);font-size:12px;width:40px;text-align:right;">${snd.volume}%</span>
        </div>
      `;
      div.querySelector('.btn-ghost').addEventListener('click', (e) => {
        AppState.mainSounds.splice(parseInt(e.currentTarget.dataset.idx), 1);
        renderMainSoundsList();
      });
      const vs = div.querySelector('.vol-slider');
      const vt = div.querySelector('span');
      vs.addEventListener('input', () => {
        vt.textContent = vs.value + '%';
        AppState.mainSounds[parseInt(vs.dataset.idx)].volume = parseInt(vs.value);
      });
      list.appendChild(div);
    });
  }

  $('soundLayerAddMainBtn')?.addEventListener('click', async () => {
    if (AppState.mainSounds.length >= 3) return;
    try {
      const path = await browseAudio();
      if (!path) return;
      setWorkspace(path);
      AppState.mainSounds.push({ path, volume: 100 });
      renderMainSoundsList();
    } catch (e) {
      toast('Gagal membuka file browser', 'error');
    }
  });

  // ── Optional sounds ──────────────────────────────────────────
  AppState.optionalSounds = AppState.optionalSounds || [];

  $('optAddSoundBtn')?.addEventListener('click', async () => {
    try {
      const path = await browseAudio();
      if (!path) return;
      let dur = 0;
      try {
        const probe = await probeFile(path);
        dur = probe?.duration ?? 0;
      } catch (_) {}
      AppState.optionalSounds.push({
        path,
        duration: dur,
        volume: 80,
        fade_in: 1.5,
        fade_out: 1.5,
        density: 'normal',
        clip_size: 'medium',
        window_start: 10,
        window_end: 90,
      });
      renderOptionalList();
    } catch (e) {
      toast('Gagal menambah file: ' + e.message, 'error');
    }
  });

  // Re-compute estimates saat target duration berubah
  $('soundLayerTargetDuration')?.addEventListener('input', () => {
    AppState.optionalSounds.forEach((_, idx) => {
      const el = $('optSoundList')?.children[idx];
      if (!el) return;
      const density   = el.querySelector(`input[name="density_${idx}"]:checked`)?.value || 'normal';
      const clip_size = el.querySelector(`input[name="clip_${idx}"]:checked`)?.value || 'medium';
      const wStart    = parseFloat(el.querySelector('.opt-wstart')?.value) || 0;
      const wEnd      = parseFloat(el.querySelector('.opt-wend')?.value)   || 100;
      const targetDur = parseFloat($('soundLayerTargetDuration')?.value) || 3600;
      const windowSec = ((wEnd - wStart) / 100) * targetDur;
      const est = $(`optEst_${idx}`);
      if (est) est.textContent = `~${calcOccurrences(windowSec, density, clip_size)}x`;
    });
  });

  // ── Plan Layers ──────────────────────────────────────────────
  $('soundLayerPreviewPlanBtn')?.addEventListener('click', async () => {
    if (AppState.mainSounds.length === 0) {
      toast('Pilih minimal 1 main sound', 'error');
      return;
    }
    if (!AppState.optionalSounds || AppState.optionalSounds.length === 0) {
      toast('Tambah minimal 1 optional sound', 'error');
      return;
    }

    logClear('soundLayerLog');
    logAppend('soundLayerLog', 'Membuat rencana penempatan...');

    const targetDuration = parseFloat($('soundLayerTargetDuration').value) || 3600;
    const loopXfade      = parseFloat($('soundLayerLoopXfade').value) || 2.0;
    const outFormat      = $('soundLayerOutputFormat').value || 'aac';

    const optional_sounds = AppState.optionalSounds.map(s => {
      const windowSec = ((s.window_end - s.window_start) / 100) * targetDuration;
      return {
        path: s.path,
        volume: s.volume,
        fade_in: s.fade_in,
        fade_out: s.fade_out,
        occurrence_count: calcOccurrences(windowSec, s.density, s.clip_size),
        min_duration: CLIP_RANGE[s.clip_size].min,
        max_duration: CLIP_RANGE[s.clip_size].max,
        time_window_start: (s.window_start / 100) * targetDuration,
        time_window_end:   (s.window_end   / 100) * targetDuration,
        min_gap: 0,
        overlap_mode: 'full',
      };
    });

    const payload = {
      main_sounds: AppState.mainSounds,
      optional_sounds,
      target_duration: targetDuration,
      loop_xfade: loopXfade,
      output_format: outFormat,
    };

    const btn = $('soundLayerPreviewPlanBtn');
    btn.disabled = true;
    try {
      const res = await previewSoundLayer(payload);
      if (res.error) {
        toast('Gagal membuat plan: ' + res.error, 'error');
        logAppend('soundLayerLog', `✗ Error: ${res.error}`, 'error');
        return;
      }
      AppState.soundLayerPlan = res;
      logClear('soundLayerLog');
      logAppend('soundLayerLog', `✓ Plan berhasil — ${res.placements.length} penempatan`, 'done');
      res.placements.forEach((p, i) => {
        const name = p.source_file.split(/[\/\\]/).pop();
        logAppend('soundLayerLog', `[${i+1}] ${name}  •  start: ${p.start_time.toFixed(1)}s  dur: ${p.duration.toFixed(1)}s`);
      });
      toast('Plan berhasil dibuat. Siap render!', 'success');
    } catch (e) {
      logAppend('soundLayerLog', `✗ Error: ${e.message}`, 'error');
      toast('Plan error: ' + e.message, 'error');
    } finally {
      btn.disabled = false;
    }
  });

  // ── Preview & Render ─────────────────────────────────────────
  $('soundLayerPreviewMixBtn')?.addEventListener('click', () => doRender(true));
  $('soundLayerRenderBtn')?.addEventListener('click', () => doRender(false));

  async function doRender(isPreview) {
    if (!AppState.soundLayerPlan) {
      toast("Klik 'Plan Layers' dahulu", 'warning');
      return;
    }

    const btn  = isPreview ? $('soundLayerPreviewMixBtn') : $('soundLayerRenderBtn');
    const orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = '⏳ Rendering...';

    const outFormat      = $('soundLayerOutputFormat').value || 'aac';
    const loopXfade      = parseFloat($('soundLayerLoopXfade').value) || 2.0;
    const targetDuration = parseFloat($('soundLayerTargetDuration').value) || 3600;

    const payload = {
      plan: AppState.soundLayerPlan,
      output_path: '',
      silence_threshold: -50,
      preview_mode: isPreview,
      output_format: outFormat,
      loop_xfade: loopXfade,
      target_duration: targetDuration,
    };

    try {
      const result = await consumeSSE(
        '/api/sound-layer/render',
        payload,
        'soundLayerLog',
        'soundLayerProgressWrap',
        'soundLayerProgressFill',
        'soundLayerProgressLabel'
      );

      if (result.ok && result.finalData?.output) {
        toast('Render selesai!', 'success');
        if (isPreview) {
          const player = $('soundLayerPlayerContainer');
          const audio  = $('soundLayerAudioPlayer');
          if (player && audio) {
            player.style.display = 'flex';
            audio.src = `/api/sound-layer/play?path=${encodeURIComponent(result.finalData.output)}&t=${Date.now()}`;
            audio.play();
          }
        }
      }
    } catch (e) {
      logAppend('soundLayerLog', `✗ ${e.message}`, 'error');
      toast(e.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = orig;
    }
  }
}
