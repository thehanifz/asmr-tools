// ═══════════════════════════════════════════════════════════════
//  Panel: Sound Layer — Per-Sound Smart Density
// ═══════════════════════════════════════════════════════════════
import { AppState, setWorkspace } from './state.js';
import { browseAudioMedia, fetchServerFiles, probeFile, previewSoundLayer } from './api.js';
import { createSoundPicker } from './sound-picker.js';
import { toast, logClear, logAppend, consumeSSE } from './ui.js';

function $(id) { return document.getElementById(id); }

// ── Density & ClipSize maps ──────────────────────────────────
const DENSITY_SPACING = { sparse: 8, normal: 4, dense: 2, vdense: 1.2 };
const CLIP_RANGE = {
  short:  { min: 3,  max: 8  },
  medium: { min: 8,  max: 20 },
  long:   { min: 20, max: 45 },
};

// Preview suara asli untuk berkas yang berasal dari Pustaka Suara server
function previewHtml(path) {
  if (!path || !path.includes('/library/')) return '';
  const src = `/api/library/play?path=${encodeURIComponent(path)}`;
  return `<audio controls preload="none" src="${src}" style="width:100%;height:34px;"></audio>`;
}

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
    <!-- Volume selalu terlihat (di luar lipatan pengaturan lanjutan) -->
    <div class="opt-row" style="padding:2px 10px 8px;">
      <label class="opt-label">Volume</label>
      <input type="range" class="slider opt-volume" min="0" max="100" value="${sound.volume}">
      <span class="opt-vol-val">${sound.volume}%</span>
    </div>
    <!-- Mode penempatan: otomatis vs atur sendiri -->
    <div class="opt-row" style="padding:0 10px 8px;align-items:center;">
      <label class="opt-label">Penempatan</label>
      <div style="display:flex;gap:6px;">
        <button type="button" class="btn btn-ghost opt-mode-btn" data-mode="auto" style="padding:4px 10px;font-size:12px;">Otomatis</button>
        <button type="button" class="btn btn-ghost opt-mode-btn" data-mode="manual" style="padding:4px 10px;font-size:12px;">Atur Sendiri</button>
      </div>
    </div>
    <!-- Panel atur sendiri -->
    <div class="opt-manual" style="display:none;padding:0 10px 6px;">
      <div class="opt-row">
        <label class="opt-label">Mulai di</label>
        <input type="number" class="input opt-mstart-v" min="0" step="1" style="width:70px;">
        <select class="input opt-mstart-u" style="width:84px;"><option value="60">menit</option><option value="1">detik</option></select>
        <span class="opt-unit">dari awal video</span>
      </div>
      <div class="opt-row">
        <label class="opt-label">Ulangi tiap</label>
        <input type="number" class="input opt-mint-v" min="0" step="1" style="width:70px;">
        <select class="input opt-mint-u" style="width:84px;"><option value="60">menit</option><option value="1">detik</option></select>
      </div>
      <div class="opt-row">
        <label class="opt-label">Durasi muncul</label>
        <input type="number" class="input opt-mdur" min="1" step="1" style="width:70px;">
        <span class="opt-unit">detik${sound.duration ? ` (isi file ${Math.round(sound.duration)} dtk)` : ''}</span>
      </div>
      <div class="opt-manual-summary" style="font-size:12px;color:var(--text-muted,#8a90a0);padding:2px 0;"></div>
    </div>
    <div class="opt-sound-body collapsed">
      <!-- Pan (posisi stereo, ala qipadd) -->
      <div class="opt-row">
        <label class="opt-label">Pan</label>
        <select class="input opt-pan" style="width:130px;">
          <option value="left" ${sound.pan==='left'?'selected':''}>Kiri</option>
          <option value="center" ${!sound.pan||sound.pan==='center'?'selected':''}>Tengah</option>
          <option value="right" ${sound.pan==='right'?'selected':''}>Kanan</option>
        </select>
        <span class="opt-unit">posisi stereo</span>
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
    const s = AppState.optionalSounds[parseInt(div.dataset.idx)];
    if (s && s.placement_mode === 'manual') { updateManualSummary(); return; }
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
    s.pan       = div.querySelector('.opt-pan')?.value || 'center';
    const man = readManual();
    s.manual_start    = man.start;
    s.manual_interval = man.interval;
    s.manual_duration = man.duration;
    updateEst();
  }

  // Volume display
  const volSlider = div.querySelector('.opt-volume');
  const volVal    = div.querySelector('.opt-vol-val');
  volSlider.addEventListener('input', () => {
    volVal.textContent = volSlider.value + '%';
    syncToState();
    window.__slRealtimeSetVolume?.('opt', parseInt(div.dataset.idx), parseInt(volSlider.value));
  });

  div.querySelectorAll('.opt-fadein, .opt-fadeout, .opt-wstart, .opt-wend').forEach(el => {
    el.addEventListener('input', syncToState);
  });
  div.querySelector('.opt-pan')?.addEventListener('change', syncToState);
  div.querySelectorAll(`input[name^="density_"], input[name^="clip_"]`).forEach(el => {
    el.addEventListener('change', syncToState);
  });

  // ── Mode penempatan: Otomatis vs Atur Sendiri ──────────────────
  function toInput(sec) {
    sec = Math.max(0, Math.round(sec || 0));
    return (sec >= 60 && sec % 60 === 0) ? { v: sec / 60, u: '60' } : { v: sec, u: '1' };
  }
  function readManual() {
    const g = (vSel, uSel) => Math.max(0, parseFloat(div.querySelector(vSel)?.value) || 0) * parseFloat(div.querySelector(uSel)?.value || '1');
    return {
      start:    g('.opt-mstart-v', '.opt-mstart-u'),
      interval: Math.max(1, g('.opt-mint-v', '.opt-mint-u')),
      duration: Math.max(1, parseFloat(div.querySelector('.opt-mdur')?.value) || 1),
    };
  }
  function fmtTime(sec) {
    sec = Math.max(0, Math.round(sec || 0));
    const m = Math.floor(sec / 60), s = sec % 60;
    return `${m}:${String(s).padStart(2, '0')}`;
  }
  function updateManualSummary() {
    const s = AppState.optionalSounds[parseInt(div.dataset.idx)];
    const sum = div.querySelector('.opt-manual-summary');
    if (!s) return;
    const targetDur = parseFloat($('soundLayerTargetDuration')?.value) || 3600;
    const cap = s.duration > 0 ? s.duration : Infinity;
    const dur = Math.min(s.manual_duration || 20, cap);
    let n = 0;
    for (let t = (s.manual_start || 0); t + dur <= targetDur && n < 2000; t += Math.max(1, s.manual_interval || 600)) n++;
    if (sum) sum.textContent = `Muncul pertama di ${fmtTime(s.manual_start || 0)}, lalu tiap ${fmtTime(s.manual_interval || 600)}, masing-masing ${Math.round(dur)} dtk → ±${n} kali dalam ${fmtTime(targetDur)}.`;
    const est = $(`optEst_${idx}`);
    if (est) est.textContent = `±${n}x`;
  }
  function applyMode(mode) {
    const s = AppState.optionalSounds[parseInt(div.dataset.idx)];
    if (s) s.placement_mode = mode;
    div.querySelectorAll('.opt-mode-btn').forEach(b => {
      const on = b.dataset.mode === mode;
      b.style.background  = on ? 'var(--accent,#f97316)' : '';
      b.style.color       = on ? '#fff' : '';
      b.style.borderColor = on ? 'transparent' : '';
    });
    div.querySelector('.opt-manual').style.display = mode === 'manual' ? '' : 'none';
    body.style.display = mode === 'manual' ? 'none' : '';
    if (mode === 'manual') updateManualSummary(); else updateEst();
  }

  const msI = toInput(sound.manual_start ?? 300);
  const miI = toInput(sound.manual_interval ?? 600);
  div.querySelector('.opt-mstart-v').value = msI.v;
  div.querySelector('.opt-mstart-u').value = msI.u;
  div.querySelector('.opt-mint-v').value   = miI.v;
  div.querySelector('.opt-mint-u').value   = miI.u;
  div.querySelector('.opt-mdur').value     = sound.manual_duration ?? 20;
  div.querySelectorAll('.opt-mode-btn').forEach(b =>
    b.addEventListener('click', () => { applyMode(b.dataset.mode); syncToState(); }));
  div.querySelectorAll('.opt-mstart-v, .opt-mstart-u, .opt-mint-v, .opt-mint-u, .opt-mdur')
    .forEach(el => el.addEventListener('input', syncToState));

  applyMode(sound.placement_mode || 'auto');
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
      const name = snd.path.split(/[\\/\\\\]/).pop();
      div.innerHTML = `
        <div style="display:flex;gap:8px;align-items:center;">
          <span title="${snd.path}" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px;">🎵 ${name}</span>
          <button class="btn btn-ghost" style="color:var(--danger);" data-idx="${idx}">Hapus</button>
        </div>
        <div style="display:flex;gap:12px;align-items:center;">
          <label style="font-size:12px;min-width:50px;">Volume</label>
          <input type="range" class="slider vol-slider" data-idx="${idx}" min="0" max="100" value="${snd.volume}" style="flex:1;">
          <span class="vol-val" style="font-family:var(--font-mono);font-size:12px;width:40px;text-align:right;">${snd.volume}%</span>
        </div>
      `;
      div.querySelector('.btn-ghost').addEventListener('click', (e) => {
        AppState.mainSounds.splice(parseInt(e.currentTarget.dataset.idx), 1);
        renderMainSoundsList();
      });
      const vs = div.querySelector('.vol-slider');
      const vt = div.querySelector('.vol-val');
      vs.addEventListener('input', () => {
        vt.textContent = vs.value + '%';
        AppState.mainSounds[parseInt(vs.dataset.idx)].volume = parseInt(vs.value);
        window.__slRealtimeSetVolume?.('main', parseInt(vs.dataset.idx), parseInt(vs.value));
      });
      list.appendChild(div);
    });
  }

  $('soundLayerAddMainBtn')?.addEventListener('click', async (e) => {
    if (AppState.mainSounds.length >= 3) return;
    const btn = e.currentTarget;
    const orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = '⏳ Memuat…';
    try {
      const path = await browseAudioMedia();
      if (!path) return;
      setWorkspace(path);
      AppState.mainSounds.push({ path, volume: 100 });
      renderMainSoundsList();
      fillLibraryPickers(); // berkas baru ikut muncul di dropdown
    } catch (err) {
      toast('Gagal menambah file: ' + err.message, 'error');
    } finally {
      btn.disabled = AppState.mainSounds.length >= 3;
      btn.textContent = orig;
    }
  });

  // ── Library pickers (Pustaka Suara di server) ───────────────
  // Dropdown kustom: klik file = preview, tombol ">" = pilih,
  // header kategori bisa expand/collapse. Lihat sound-picker.js.
  const mainLibPicker = createSoundPicker({
    id: 'soundLayerMainLibPicker',
    placeholder: '🎧 Pilih dari Pustaka Suara…',
    onSelect: (item) => {
      if (AppState.mainSounds.length >= 3) {
        toast('Main sound maksimal 3', 'error');
        return;
      }
      setWorkspace(item.path);
      AppState.mainSounds.push({ path: item.path, volume: 100 });
      renderMainSoundsList();
    },
  });
  $('soundLayerMainList')?.before(mainLibPicker.root);

  const optLibPicker = createSoundPicker({
    id: 'optLibPicker',
    placeholder: '🎧 Pilih dari Pustaka Suara…',
    onSelect: (item) => {
      AppState.optionalSounds.push({
        path: item.path,
        duration: item.duration || 0,
        volume: 80,
        pan: 'center',
        fade_in: 1.5,
        fade_out: 1.5,
        density: 'normal',
        clip_size: 'medium',
        window_start: 0,
        window_end: 100,
        placement_mode: 'auto',
        manual_start: 300,
        manual_interval: 600,
        manual_duration: 20,
      });
      renderOptionalList();
    },
  });
  $('optSoundList')?.before(optLibPicker.root);

  async function fillLibraryPickers() {
    try {
      // Katalog lengkap: Audio di Server + Pustaka Suara (grup media ditaruh
      // terakhir supaya kategori Hujan tetap yang pertama terbuka).
      const data = await fetchServerFiles('audio');
      const groups = (data.groups || []).slice().sort(
        (a, b) => (a.element === 'media-audio' ? 1 : 0) - (b.element === 'media-audio' ? 1 : 0)
      );
      mainLibPicker.setGroups(groups);
      optLibPicker.setGroups(groups);
    } catch (e) {
      mainLibPicker.setError();
      optLibPicker.setError();
    }
  }
  fillLibraryPickers();

  // ── Optional sounds ──────────────────────────────────────────
  AppState.optionalSounds = AppState.optionalSounds || [];

  $('optAddSoundBtn')?.addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    const orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = '⏳ Memuat…';
    try {
      const path = await browseAudioMedia();
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
        pan: 'center',
        fade_in: 1.5,
        fade_out: 1.5,
        density: 'normal',
        clip_size: 'medium',
        window_start: 0,
        window_end: 100,
        placement_mode: 'auto',
        manual_start: 300,
        manual_interval: 600,
        manual_duration: 20,
      });
      renderOptionalList();
      fillLibraryPickers(); // berkas baru ikut muncul di dropdown
    } catch (err) {
      toast('Gagal menambah file: ' + err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = orig;
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
      const est = $(`optEst_${idx}`);
      const s = AppState.optionalSounds[idx];
      if (s && s.placement_mode === 'manual') {
        const cap = s.duration > 0 ? s.duration : Infinity;
        const dur = Math.min(s.manual_duration || 20, cap);
        let n = 0;
        for (let t = (s.manual_start || 0); t + dur <= targetDur && n < 2000; t += Math.max(1, s.manual_interval || 600)) n++;
        if (est) est.textContent = `±${n}x`;
        const sum = el.querySelector('.opt-manual-summary');
        if (sum) {
          const ft = (sec) => { sec = Math.max(0, Math.round(sec || 0)); return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`; };
          sum.textContent = `Muncul pertama di ${ft(s.manual_start || 0)}, lalu tiap ${ft(s.manual_interval || 600)}, masing-masing ${Math.round(dur)} dtk → ±${n} kali dalam ${ft(targetDur)}.`;
        }
        return;
      }
      const windowSec = ((wEnd - wStart) / 100) * targetDur;
      if (est) est.textContent = `~${calcOccurrences(windowSec, density, clip_size)}x`;
    });
  });

  // ── Plan Layers ──────────────────────────────────────────────
  $('soundLayerPreviewPlanBtn')?.addEventListener('click', async () => {
    if (AppState.mainSounds.length === 0) {
      toast('Pilih minimal 1 main sound', 'error');
      return;
    }
    // Remove the requirement for optional sounds
    // if (!AppState.optionalSounds || AppState.optionalSounds.length === 0) {
    //   toast('Tambah minimal 1 optional sound', 'error');
    //   return;
    // }

    logClear('soundLayerLog');
    logAppend('soundLayerLog', 'Membuat rencana penempatan...');

    const targetDuration = parseFloat($('soundLayerTargetDuration').value) || 3600;
    const loopXfade      = parseFloat($('soundLayerLoopXfade').value) || 2.0;
    const outFormat      = $('soundLayerOutputFormat').value || 'm4a';

    const optional_sounds = AppState.optionalSounds.map(s => {
      const windowSec = ((s.window_end - s.window_start) / 100) * targetDuration;
      return {
        path: s.path,
        volume: s.volume,
        pan: s.pan || 'center',
        fade_in: s.fade_in,
        fade_out: s.fade_out,
        occurrence_count: calcOccurrences(windowSec, s.density, s.clip_size),
        min_duration: CLIP_RANGE[s.clip_size].min,
        max_duration: CLIP_RANGE[s.clip_size].max,
        time_window_start: (s.window_start / 100) * targetDuration,
        time_window_end:   (s.window_end   / 100) * targetDuration,
        min_gap: 0,
        overlap_mode: 'full',
        placement_mode: s.placement_mode || 'auto',
        manual_start: s.manual_start ?? 300,
        manual_interval: s.manual_interval ?? 600,
        manual_duration: s.manual_duration ?? 20,
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

    // Update main sounds and placement volumes in the plan to match current state/UI
    if (AppState.soundLayerPlan) {
      AppState.soundLayerPlan.main_sounds = AppState.mainSounds.map(snd => ({
        path: snd.path,
        volume: snd.volume
      }));

      const optVolMap = {};
      const optPanMap = {};
      AppState.optionalSounds.forEach(s => {
        optVolMap[s.path] = s.volume;
        optPanMap[s.path] = s.pan || 'center';
      });

      AppState.soundLayerPlan.placements.forEach(p => {
        if (optVolMap[p.source_file] !== undefined) {
          p.volume = optVolMap[p.source_file];
        }
        if (optPanMap[p.source_file] !== undefined) {
          p.pan = optPanMap[p.source_file];
        }
      });
    }

    const outFormat      = $('soundLayerOutputFormat').value || 'm4a';
    const loopXfade      = parseFloat($('soundLayerLoopXfade').value) || 2.0;
    const targetDuration = parseFloat($('soundLayerTargetDuration').value) || 3600;
    const previewDuration = parseFloat($('soundLayerPreviewDuration')?.value) || 30.0;

    const payload = {
      plan: AppState.soundLayerPlan,
      output_path: '',
      silence_threshold: -50,
      preview_mode: isPreview,
      output_format: outFormat,
      loop_xfade: loopXfade,
      target_duration: targetDuration,
      preview_duration: previewDuration,
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
        if (!isPreview) {
          // Hand the finished mix to the Merge panel (auto-fill source)
          AppState.soundLayerOutputPath = result.finalData.output;
          setWorkspace(result.finalData.output);
        }
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

  // ── Preview Realtime (Web Audio — streaming, tanpa render) ────
  // Semua main sound + backsound diputar barengan sebagai loop dari
  // browser. Slider volume tiap track langsung mengubah gain yang
  // sedang berputar lewat window.__slRealtimeSetVolume.
  const rt = { ctx: null, nodes: [], playing: false };
  const rtDefaultStatus = 'Preview realtime: semua main sound + backsound diputar barengan langsung dari browser (streaming, tanpa render). Geser slider volume tiap track — perubahannya langsung terdengar. Optional sound diputar loop untuk cek blend; di render asli ia muncul berkala. Kalau tambah/hapus track, Stop lalu Putar lagi.';
  const rtStatus = (msg) => { const el = $('slRealtimeStatus'); if (el) el.textContent = msg; };

  function rtCollect() {
    const tracks = [];
    (AppState.mainSounds || []).forEach((s, i) => {
      if (s.path) tracks.push({ kind: 'main', idx: i, path: s.path, volume: s.volume ?? 100, pan: 0 });
    });
    (AppState.optionalSounds || []).forEach((s, i) => {
      if (s.path) tracks.push({ kind: 'opt', idx: i, path: s.path, volume: s.volume ?? 80,
        pan: s.pan === 'left' ? -0.6 : s.pan === 'right' ? 0.6 : 0 });
    });
    return tracks;
  }

  function rtStop() {
    rt.nodes.forEach(n => { try { n.src.stop(); } catch (_) {} });
    rt.nodes = [];
    if (rt.ctx) { rt.ctx.close().catch(() => {}); rt.ctx = null; }
    rt.playing = false;
    const pb = $('slRealtimePlayBtn'), sb = $('slRealtimeStopBtn');
    if (pb) { pb.disabled = false; pb.textContent = '▶ Preview Realtime'; }
    if (sb) sb.disabled = true;
  }

  window.__slRealtimeSetVolume = (kind, idx, vol) => {
    const n = rt.nodes.find(x => x.kind === kind && x.idx === idx);
    if (n && rt.ctx) n.gain.gain.setTargetAtTime((vol || 0) / 100, rt.ctx.currentTime, 0.03);
  };

  $('slRealtimePlayBtn')?.addEventListener('click', async () => {
    const pb = $('slRealtimePlayBtn'), sb = $('slRealtimeStopBtn');
    if (rt.playing && rt.ctx) {
      if (rt.ctx.state === 'running') { await rt.ctx.suspend(); pb.textContent = '▶ Lanjut Putar'; rtStatus('Preview realtime dijeda.'); }
      else { await rt.ctx.resume(); pb.textContent = '⏸ Jeda'; rtStatus('▶ Preview realtime berputar…'); }
      return;
    }
    const tracks = rtCollect();
    if (!tracks.length) { toast('Tambah minimal 1 main sound atau backsound dulu', 'error'); return; }
    rtStop();
    pb.disabled = true; pb.textContent = '⏳ Memuat…';
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      rt.ctx = ctx;
      const master = ctx.createGain(); master.gain.value = 0.9; master.connect(ctx.destination);
      rtStatus(`Memuat ${tracks.length} track…`);
      for (const t of tracks) {
        const res = await fetch(`/api/sound-layer/play?path=${encodeURIComponent(t.path)}`);
        if (!res.ok) throw new Error('Gagal memuat ' + t.path.split('/').pop());
        const buf = await ctx.decodeAudioData(await res.arrayBuffer());
        const src = ctx.createBufferSource(); src.buffer = buf; src.loop = true;
        const gain = ctx.createGain(); gain.gain.value = (t.volume || 0) / 100;
        const panner = ctx.createStereoPanner(); panner.pan.value = t.pan || 0;
        src.connect(gain); gain.connect(panner); panner.connect(master);
        rt.nodes.push({ ...t, src, gain });
      }
      const t0 = ctx.currentTime + 0.05;
      rt.nodes.forEach(n => n.src.start(t0));
      rt.playing = true;
      pb.disabled = false; pb.textContent = '⏸ Jeda';
      if (sb) sb.disabled = false;
      rtStatus(`▶ Memutar ${rt.nodes.length} track barengan. Geser slider volume tiap track — langsung terdengar.`);
    } catch (e) {
      rtStop();
      rtStatus(rtDefaultStatus);
      toast('Preview realtime gagal: ' + e.message, 'error');
    }
  });

  $('slRealtimeStopBtn')?.addEventListener('click', () => { rtStop(); rtStatus('Preview realtime berhenti.'); });
}
