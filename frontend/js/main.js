// ═══════════════════════════════════════════════
//  Main — sidebar routing + module init
// ═══════════════════════════════════════════════
import { initVideo }     from './panel-video.js';
import { initAudio }     from './panel-audio.js';
import { initDenoise }   from './panel-denoise.js';
import { initMerge }     from './panel-merge.js';
import { initThumbnail } from './panel-thumbnail.js';

const TOOLS = ['video', 'audio', 'denoise', 'merge', 'thumbnail'];

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
initVideo();
initAudio();
initDenoise();
initMerge();
initThumbnail();

// Default: video
activateTool('video');
