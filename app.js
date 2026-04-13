// ── STATE ────────────────────────────────────────────────────────────────
let fileInfo = {};
let lastOutputFolder = '';
let pipelineState = { original: '', lastOutput: '', chain: [] };

// live timer
let _timerInterval = null;
let _stepStartTime = null;
let _totalStartTime = null;

// ── DRAG & DROP ───────────────────────────────────────────────────────
const dropZone = document.getElementById('drop-zone');
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) {
    const pathInput = document.getElementById('file-path');
    if (file.path && file.path.includes(os_sep())) {
      pathInput.value = file.path;
      probeVideo();
    } else {
      pathInput.value = file.name;
      pathInput.style.borderColor = '#e94560';
      setLog('\u26A0\uFE0F Drag & Drop hanya mendapat nama file. Gunakan tombol \uD83D\uDCC2 Browse.');
    }
  }
});

function os_sep() { return navigator.platform.includes('Win') ? '\\' : '/'; }

// ── BROWSE ────────────────────────────────────────────────────────
async function browseFile() {
  try {
    const res = await fetch('/api/browse');
    const data = await res.json();
    if (data.error) return setLog('\u274C Browse error: ' + data.error);
    if (data.path) {
      document.getElementById('file-path').value = data.path;
      document.getElementById('file-path').style.borderColor = '';
      probeVideo();
    }
  } catch (err) { setLog('\u274C Browse gagal: ' + err.message); }
}

async function browseOutputFolder(targetId) {
  try {
    const res = await fetch('/api/browse-folder');
    const data = await res.json();
    if (data.error) return setLog('\u274C Browse folder error: ' + data.error);
    if (data.path && targetId) {
      const el = document.getElementById(targetId);
      if (el) {
        const base = (fileInfo.filename || 'video').replace(/\.[^.]+$/, '');
        const sep  = os_sep();
        if (targetId === 'all-output-dir') {
          el.value = data.path;
        } else {
          const suffixMap = {
            'crop-output'      : `${sep}${base}_cropped.mp4`,
            'upscale-output'   : `${sep}${base}_1080p.mp4`,
            'loop-output'      : `${sep}${base}_loop.mp4`,
            'audio-output'     : `${sep}${base}_audio.mp4`,
            'thumb-output'     : `${sep}${base}_thumbnail.jpg`,
            'audio-custom-path': '',
            'extract-output'   : `${sep}${base}_audio.mp3`,
          };
          el.value = data.path + (suffixMap[targetId] !== undefined ? suffixMap[targetId] : '');
        }
        lastOutputFolder = data.path;
      }
    }
  } catch (err) { setLog('\u274C Browse folder gagal: ' + err.message); }
}

// ── PROBE VIDEO ──────────────────────────────────────────────────────
async function probeVideo() {
  const path = document.getElementById('file-path').value.trim();
  if (!path) return alert('Masukkan path video dulu!');
  setLog('\u23F3 Membaca info video...');
  try {
    const res  = await fetch('/api/probe', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({path}) });
    const data = await res.json();
    if (data.error) return setLog('\u274C ' + data.error);
    fileInfo = { ...data, path };
    pipelineState = { original: path, lastOutput: path, chain: [] };
    updatePipelineIndicator();
    document.getElementById('info-name').textContent     = data.filename;
    document.getElementById('info-duration').textContent = data.duration_str;
    document.getElementById('info-res').textContent      = data.resolution;
    document.getElementById('info-fps').textContent      = data.fps + ' fps';
    document.getElementById('info-size').textContent     = data.size_str;
    document.getElementById('file-info').classList.remove('hidden');
    autoFillOutputs(path);
    setLog(`\u2705 File loaded: ${data.filename} (${data.resolution}, ${data.duration_str}, ${data.size_str})`);
  } catch (err) { setLog('\u274C Error: ' + err.message); }
}

function autoFillOutputs(inputPath) {
  const sep  = os_sep();
  const dir  = inputPath.includes(sep)
    ? inputPath.substring(0, inputPath.lastIndexOf(sep))
    : inputPath.substring(0, inputPath.lastIndexOf('/'));
  const base = (fileInfo.filename || 'video').replace(/\.[^.]+$/, '');
  document.getElementById('crop-output').value    = `${dir}${sep}${base}_cropped.mp4`;
  document.getElementById('upscale-output').value = `${dir}${sep}${base}_1080p.mp4`;
  document.getElementById('loop-output').value    = `${dir}${sep}${base}_loop.mp4`;
  document.getElementById('audio-output').value   = `${dir}${sep}${base}_audio.mp4`;
  document.getElementById('thumb-output').value   = `${dir}${sep}${base}_thumbnail.jpg`;
  document.getElementById('all-output-dir').value = dir;
  // FIX #3: isi extract-input secara otomatis saat file di-load
  const extractInput = document.getElementById('extract-input');
  if (extractInput) extractInput.value = inputPath;
  lastOutputFolder = dir;
}

// ── PIPELINE STATE ────────────────────────────────────────────────────
function updatePipelineIndicator() {
  const el = document.getElementById('pipeline-indicator');
  if (!el) return;
  if (!pipelineState.lastOutput) { el.classList.add('hidden'); return; }
  el.classList.remove('hidden');
  const fname = pipelineState.lastOutput.split('\\').pop().split('/').pop();
  const isOriginal = pipelineState.lastOutput === pipelineState.original;
  el.innerHTML = `<span>\uD83C\uDFAF Input aktif: <strong>${fname}</strong></span>
    ${!isOriginal ? `<button onclick="resetPipeline()">↩ Reset</button>` : ''}`;
}

function resetPipeline() {
  pipelineState.lastOutput = pipelineState.original;
  pipelineState.chain = [];
  updatePipelineIndicator();
  setLog('\u21A9 Pipeline direset ke file original: ' + pipelineState.original);
}

function setLastOutput(outputPath, stepName) {
  pipelineState.lastOutput = outputPath;
  pipelineState.chain.push({ step: stepName, output: outputPath });
  updatePipelineIndicator();
  const sep = os_sep();
  const dir = outputPath.includes(sep)
    ? outputPath.substring(0, outputPath.lastIndexOf(sep))
    : outputPath.substring(0, outputPath.lastIndexOf('/'));
  lastOutputFolder = dir;
}

// ── DURATION LABEL ───────────────────────────────────────────────
document.getElementById('loop-duration').addEventListener('input', function() {
  const sec = parseInt(this.value) || 0;
  const h   = Math.floor(sec / 3600);
  const m   = Math.floor((sec % 3600) / 60);
  document.getElementById('duration-label').textContent = `= ${h} jam ${m} menit`;
});

function setDuration(sec) {
  document.getElementById('loop-duration').value = sec;
  document.getElementById('loop-duration').dispatchEvent(new Event('input'));
}

// ── LOOP MODE TOGGLE ───────────────────────────────────────────────────
function updateLoopModeUI() {
  const mode = document.getElementById('loop-mode').value;
  const noiseRow    = document.getElementById('loop-noise-row');
  const v2Info      = document.getElementById('loop-v2-info');
  const crossfadeRow = document.getElementById('loop-crossfade-row');
  if (noiseRow)     noiseRow.classList.toggle('hidden', mode === 'v2');
  if (v2Info)       v2Info.classList.toggle('hidden', mode !== 'v2');
  if (crossfadeRow) crossfadeRow.classList.toggle('hidden', mode !== 'v2');
}

// ── AUDIO CUSTOM TOGGLE ────────────────────────────────────────────────
document.getElementById('audio-noise').addEventListener('change', function() {
  document.getElementById('audio-custom-row').classList.toggle('hidden', this.value !== 'custom');
});

// ── LIVE TIMER HELPERS ──────────────────────────────────────────────────
function fmtSec(s) {
  s = Math.floor(s);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}j ${String(m).padStart(2,'0')}m ${String(sec).padStart(2,'0')}s`;
  if (m > 0) return `${m}m ${String(sec).padStart(2,'0')}s`;
  return `${sec}s`;
}

function startLiveTimer() {
  _stepStartTime  = Date.now();
  if (!_totalStartTime) _totalStartTime = Date.now();
  clearInterval(_timerInterval);
  _timerInterval = setInterval(() => {
    const stepElapsed  = (Date.now() - _stepStartTime) / 1000;
    const totalElapsed = (Date.now() - _totalStartTime) / 1000;
    document.getElementById('timer-step').textContent  = fmtSec(stepElapsed);
    document.getElementById('timer-total').textContent = fmtSec(totalElapsed);
  }, 500);
}

function stopLiveTimer() {
  clearInterval(_timerInterval);
  _timerInterval = null;
}

function resetTimers() {
  stopLiveTimer();
  _stepStartTime = null;
  _totalStartTime = null;
  document.getElementById('timer-step').textContent  = '0s';
  document.getElementById('timer-total').textContent = '0s';
}

// ── RUN SINGLE PROCESS ───────────────────────────────────────────────────
async function runProcess(action) {
  if (!pipelineState.lastOutput && !fileInfo.path) return alert('Load video dulu!');
  const input = pipelineState.lastOutput || fileInfo.path;
  let params = { input };

  if (action === 'crop') {
    params.output = document.getElementById('crop-output').value;
    params.pixels = parseInt(document.getElementById('crop-px').value);
  } else if (action === 'upscale') {
    if (fileInfo.height >= 1080) return alert('Resolusi sudah 1080p atau lebih, skip upscale.');
    params.output = document.getElementById('upscale-output').value;
    params.algo   = document.getElementById('upscale-algo').value;
    params.crf    = parseInt(document.getElementById('upscale-crf').value);
  } else if (action === 'loop') {
    params.output         = document.getElementById('loop-output').value;
    params.duration       = parseInt(document.getElementById('loop-duration').value);
    params.video_duration = fileInfo.duration || 8;
    params.fps            = fileInfo.fps || 24;
    params.noise          = 'brown';
    params.mode           = document.getElementById('loop-mode').value;
    if (params.mode === 'v2') {
      if (!params.output) return alert('Isi output path dulu!');
      params.crossfade = parseFloat(document.getElementById('loop-crossfade')?.value || '0.3');
      const outputPath = params.output;
      startStream('/api/loop-v2', { params }, () => setLastOutput(outputPath, 'loop-v2'));
      return;
    }
  } else if (action === 'audio') {
    params.output    = document.getElementById('audio-output').value;
    params.noise     = document.getElementById('audio-noise').value;
    params.duration  = fileInfo.duration || 3600;
    if (params.noise === 'custom')
      params.custom_audio = document.getElementById('audio-custom-path').value;
  } else if (action === 'thumbnail') {
    params.input      = pipelineState.original || fileInfo.path;
    params.output     = document.getElementById('thumb-output').value;
    params.text1      = document.getElementById('thumb-text1').value;
    params.text2      = document.getElementById('thumb-text2').value;
    params.size1      = parseInt(document.getElementById('thumb-size1').value);
    params.color      = document.getElementById('thumb-color').value.replace('#', '');
    params.frame_time = parseInt(document.getElementById('thumb-frame').value);
  }

  if (!params.output) return alert('Isi output path dulu!');
  const outputPath = params.output;
  startStream('/api/process', { action, params }, () => {
    if (action !== 'thumbnail') setLastOutput(outputPath, action);
  });
}

// ── RUN ALL IN ONE ─────────────────────────────────────────────────────────
async function runProcessAll() {
  if (!fileInfo.path) return alert('Load video dulu!');
  const body = {
    input          : pipelineState.original || fileInfo.path,
    output_dir     : document.getElementById('all-output-dir').value,
    crop_px        : parseInt(document.getElementById('all-crop-px').value),
    upscale        : document.getElementById('all-upscale').checked,
    target_duration: parseInt(document.getElementById('all-duration').value),
    video_duration : fileInfo.duration || 8,
    fps            : fileInfo.fps || 24,
    noise_color    : document.getElementById('all-noise').value,
    loop_mode      : document.getElementById('all-loop-mode')?.value || 'v2',
    crossfade      : parseFloat(document.getElementById('all-crossfade')?.value || '0.3'),
    thumb_text1    : document.getElementById('all-thumb1').value,
    thumb_text2    : document.getElementById('all-thumb2').value,
  };
  lastOutputFolder = body.output_dir;
  startStream('/api/process-all', body);
}

// ── SSE STREAM ───────────────────────────────────────────────────────────────
function startStream(endpoint, body, onDoneCallback) {
  clearLog();
  resetTimers();
  setProgress(0, '\u23F3 Memulai proses...');
  document.getElementById('btn-open-folder').classList.add('hidden');
  document.getElementById('timer-box').classList.remove('hidden');

  fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  }).then(res => {
    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    function read() {
      reader.read().then(({ done, value }) => {
        if (done) { stopLiveTimer(); return; }
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();
        lines.forEach(line => {
          if (line.startsWith('data: ')) {
            try { handleStreamData(JSON.parse(line.slice(6)), onDoneCallback); } catch(e) {}
          }
        });
        read();
      });
    }
    read();
  }).catch(err => { stopLiveTimer(); setLog('\u274C ' + err.message); });
}

function handleStreamData(d, onDoneCallback) {
  if (d.type === 'pipeline_start') {
    _totalStartTime = Date.now();
    appendLog('='.repeat(52));
    appendLog(`\uD83D\uDE80 ALL-IN-ONE PIPELINE DIMULAI`);
    appendLog(`   Input   : ${d.input} (${d.input_size})`);
    appendLog(`   Target  : ${d.target} | Mode: ${d.loop_mode.toUpperCase()}`);
    appendLog(`   Total step: ${d.total_steps}`);
    appendLog('='.repeat(52));
    return;
  }

  if (d.type === 'step_start') {
    startLiveTimer();
    appendLog('');
    appendLog(`\u25B6\uFE0F  [${d.step}/${d.total}] ${d.label}`);
    appendLog(`   CMD: ${d.cmd}`);
    setProgress(Math.round(((d.step - 1) / d.total) * 90), `Step ${d.step}/${d.total}: ${d.label}`);
    return;
  }

  if (d.type === 'step_done') {
    startLiveTimer();
    const pct = Math.round((d.step / d.total) * 90);
    setProgress(pct, `\u2705 Step ${d.step}/${d.total} selesai`);
    appendLog(`\u2705  Selesai dalam ${d.elapsed} | Output: ${d.output_file} (${d.output_size})`);
    return;
  }

  if (d.type === 'step_error') {
    stopLiveTimer();
    appendLog(`\u274C  ERROR di step ${d.step}: ${d.label} (${d.elapsed})`);
    setProgress(0, `\u274C Error di step ${d.step}`);
    return;
  }

  if (d.log) {
    appendLog('   ' + d.log);
    const match = d.log.match(/frame=\s*(\d+)/);
    if (match) {
      const frame = parseInt(match[1]);
      const totalFrames = Math.round((fileInfo.duration || 8) * (fileInfo.fps || 24) * 450);
      const pct = Math.min(89, Math.round((frame / totalFrames) * 100));
      setProgress(pct, `\u23F3 frame ${frame}`);
    }
    if (d.log.includes('speed=')) {
      const m = d.log.match(/speed=(\S+)x/);
      if (m) document.getElementById('progress-info').textContent += `  \u26A1 ${m[1]}x`;
    }
  }

  if (d.step_done) {
    appendLog(`\u2705  Step ${d.step_done} selesai (${d.elapsed}) \u2192 ${d.output_file} (${d.output_size})`);
    startLiveTimer();
  }

  if (d.status === 'done' || d.status === 'all_done') {
    stopLiveTimer();
    setProgress(100, `\u2705 Selesai!`);
    document.getElementById('btn-open-folder').classList.remove('hidden');
    appendLog('');
    appendLog('='.repeat(52));
    appendLog(`\u2705  PIPELINE SELESAI`);
    if (d.total_elapsed) appendLog(`\u23F1\uFE0F  Total waktu   : ${d.total_elapsed}`);
    if (d.output)        appendLog(`\uD83D\uDCF9  Output video  : ${d.output}`);
    if (d.final_size)    appendLog(`\uD83D\uDCBE  Ukuran output : ${d.final_size}`);
    if (d.thumbnail)     appendLog(`\uD83D\uDDBC\uFE0F  Thumbnail     : ${d.thumbnail} (${d.thumb_size || '?'})`);
    if (d.tmp) {
      appendLog(`\uD83D\uDDC2\uFE0F  Temp files:`);
      Object.entries(d.tmp).forEach(([k, v]) => appendLog(`     ${k}: ${v}`));
    }
    appendLog('='.repeat(52));
    if (onDoneCallback) onDoneCallback();
  }

  if (d.status === 'error') {
    stopLiveTimer();
    setProgress(0, '\u274C Error! Lihat log di bawah.');
  }
}

// ── OPEN FOLDER ───────────────────────────────────────────────────────────
async function openFolder() {
  await fetch('/api/open-folder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ folder: lastOutputFolder })
  });
}

// ── LOG HELPERS ───────────────────────────────────────────────────────────
function setLog(msg) {
  const box = document.getElementById('log-box');
  box.textContent = msg;
  box.scrollTop = box.scrollHeight;
}
function appendLog(msg) {
  const box = document.getElementById('log-box');
  box.textContent += msg + '\n';
  box.scrollTop = box.scrollHeight;
}
function clearLog() {
  document.getElementById('log-box').textContent = '';
}
function setProgress(pct, label) {
  if (pct !== null) document.getElementById('progress-bar').style.width = pct + '%';
  if (label)        document.getElementById('progress-info').textContent = label;
}
