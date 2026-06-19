// ═══════════════════════════════════════════════
//  Main — sidebar routing + module init
// ═══════════════════════════════════════════════
import { initCrop }       from './panel-crop.js';
import { initVideo }      from './panel-video.js';
import { initExtract }    from './panel-extract.js';
import { initSoundLayer } from './panel-sound-layer.js';
import { initDenoise }    from './panel-denoise.js';
import { initMerge }      from './panel-merge.js';
import { initConcat }     from './panel-concat.js';
import { initLoopBA }     from './panel-loop-ba.js';
import { initThumbnail }  from './panel-thumbnail.js';
import { initLive }       from './panel-live.js';
import { AppState }       from './state.js';
import { toast }          from './ui.js';

const TOOLS = ['crop', 'concat', 'loop-ba', 'video', 'sound-layer', 'merge', 'extract', 'denoise', 'thumbnail', 'live'];

function activateTool(name) {
  TOOLS.forEach(t => {
    document.getElementById(`tool-${t}`)?.classList.toggle('hidden', t !== name);
    document.querySelector(`.nav-item[data-tool="${t}"]`)?.classList.toggle('active', t === name);
  });
}

document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => activateTool(btn.dataset.tool));
});

// Init all panels
initCrop();
initConcat();
initLoopBA();
initVideo();
initSoundLayer();
initMerge();
initExtract();
initDenoise();
initThumbnail();
initLive();

// Default: crop
activateTool('crop');

// ── Auto Cleanup ──────────────────────────────────────────────────
document.getElementById('btnAutoCleanup')?.addEventListener('click', async () => {
  if (!AppState.workspaceDir) {
    toast('Workspace belum aktif. Buka file video/audio dulu.', 'error');
    return;
  }
  
  if (!confirm(`Hapus semua file temporary (_tmp_*) di workspace ini?\n\n${AppState.workspaceDir}`)) {
    return;
  }

  const btn = document.getElementById('btnAutoCleanup');
  const origText = btn.innerHTML;
  btn.innerHTML = '<span class="loading-spinner"></span> Cleaning...';
  btn.disabled = true;

  try {
    const res = await fetch('/api/cleanup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace: AppState.workspaceDir })
    });
    const data = await res.json();
    
    if (data.status === 'success') {
      toast(data.message, 'success');
    } else {
      toast('Gagal: ' + data.message, 'error');
    }
  } catch (err) {
    toast('Error saat cleanup: ' + err.message, 'error');
  } finally {
    btn.innerHTML = origText;
    btn.disabled = false;
  }
});
