let fileInfo = {};
let lastOutputFolder = '';

// ── DRAG & DROP ──────────────────────────────────────────────
const dropZone = document.getElementById('drop-zone');

dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));

dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) {
    document.getElementById('file-path').value = file.path || file.name;
    probeVideo();
  }
});

// ── PROBE VIDEO ──────────────────────────────────────────────
async function probeVideo() {
  const path = document.getElementById('file-path').value.trim();
  if (!path) return alert('Masukkan path video dulu!');
  setLog('⏳ Membaca info video...');
  try {
    const res = await fetch('/api/probe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path })
    });
    const data = await res.json();
    if (data.error) return setLog('❌ ' + data.error);
    fileInfo = { ...data, path };
    document.getElementById('info-name').textContent = data.filename;
    document.getElementById('info-duration').textContent = data.duration_str;
    document.getElementById('info-res').textContent = data.resolution;
    document.getElementById('info-fps').textContent = data.fps + ' fps';
    document.getElementById('info-size').textContent = data.size_str;
    document.getElementById('file-info').classList.remove('hidden');
    autoFillOutputs(path);
    setLog(`✅ File loaded: ${data.filename} (${data.resolution}, ${data.duration_str})`);
  } catch (err) {
    setLog('❌ Error: ' + err.message);
  }
}

function autoFillOutputs(inputPath) {
  const dir = inputPath.includes('\\') 
    ? inputPath.substring(0, inputPath.lastIndexOf('\\'))
    : inputPath.substring(0, inputPath.lastIndexOf('/'));
  const base = (fileInfo.filename || 'video').replace(/\.[^.]+$/, '');
  document.getElementById('crop-output').value = `${dir}\\${base}_cropped.mp4`;
  document.getElementById('upscale-output').value = `${dir}\\${base}_1080p.mp4`;
  document.getElementById('loop-output').value = `${dir}\\${base}_loop.mp4`;
  document.getElementById('audio-output').value = `${dir}\\${base}_audio.mp4`;
  document.getElementById('thumb-output').value = `${dir}\\${base}_thumbnail.jpg`;
  document.getElementById('all-output-dir').value = dir;
  lastOutputFolder = dir;
}

// ── TABS ─────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  event.target.classList.add('active');
}

// ── DURATION LABEL ───────────────────────────────────────────
document.getElementById('loop-duration').addEventListener('input', function() {
  const sec = parseInt(this.value) || 0;
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  document.getElementById('duration-label').textContent = `= ${h} jam ${m} menit`;
});

function setDuration(sec) {
  document.getElementById('loop-duration').value = sec;
  document.getElementById('loop-duration').dispatchEvent(new Event('input'));
}

// ── AUDIO CUSTOM TOGGLE ──────────────────────────────────────
document.getElementById('audio-noise').addEventListener('change', function() {
  document.getElementById('audio-custom-row').classList.toggle('hidden', this.value !== 'custom');
});

// ── RUN SINGLE PROCESS ───────────────────────────────────────
async function runProcess(action) {
  if (!fileInfo.path) return alert('Load video dulu!');
  const input = fileInfo.path;
  let params = { input };

  if (action === 'crop') {
    params.output = document.getElementById('crop-output').value;
    params.pixels = parseInt(document.getElementById('crop-px').value);
  } else if (action === 'upscale') {
    if (fileInfo.height >= 1080) return alert('Resolusi sudah 1080p atau lebih, skip upscale.');
    params.output = document.getElementById('upscale-output').value;
  } else if (action === 'loop') {
    params.output = document.getElementById('loop-output').value;
    params.duration = parseInt(document.getElementById('loop-duration').value);
    params.video_duration = fileInfo.duration || 8;
    params.fps = fileInfo.fps || 24;
    params.noise = 'brown';
  } else if (action === 'audio') {
    params.output = document.getElementById('audio-output').value;
    params.noise = document.getElementById('audio-noise').value;
    params.duration = fileInfo.duration || 3600;
    if (params.noise === 'custom') {
      params.custom_audio = document.getElementById('audio-custom-path').value;
    }
  } else if (action === 'thumbnail') {
    params.output = document.getElementById('thumb-output').value;
    params.text1 = document.getElementById('thumb-text1').value;
    params.text2 = document.getElementById('thumb-text2').value;
    params.size1 = parseInt(document.getElementById('thumb-size1').value);
    params.color = document.getElementById('thumb-color').value.replace('#', '');
    params.frame_time = parseInt(document.getElementById('thumb-frame').value);
  }

  if (!params.output) return alert('Isi output path dulu!');
  lastOutputFolder = params.output.includes('\\') 
    ? params.output.substring(0, params.output.lastIndexOf('\\'))
    : params.output.substring(0, params.output.lastIndexOf('/'));

  startStream('/api/process', { action, params });
}

// ── RUN ALL IN ONE ───────────────────────────────────────────
async function runProcessAll() {
  if (!fileInfo.path) return alert('Load video dulu!');
  const body = {
    input: fileInfo.path,
    output_dir: document.getElementById('all-output-dir').value,
    crop_px: parseInt(document.getElementById('all-crop-px').value),
    upscale: document.getElementById('all-upscale').checked,
    target_duration: parseInt(document.getElementById('all-duration').value),
    video_duration: fileInfo.duration || 8,
    fps: fileInfo.fps || 24,
    noise_color: document.getElementById('all-noise').value,
    thumb_text1: document.getElementById('all-thumb1').value,
    thumb_text2: document.getElementById('all-thumb2').value,
  };
  lastOutputFolder = body.output_dir;
  startStream('/api/process-all', body);
}

// ── SSE STREAM ───────────────────────────────────────────────
function startStream(endpoint, body) {
  clearLog();
  setProgress(0, '⏳ Memulai proses...');
  document.getElementById('btn-open-folder').classList.add('hidden');

  fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  }).then(res => {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    function read() {
      reader.read().then(({ done, value }) => {
        if (done) return;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();
        lines.forEach(line => {
          if (line.startsWith('data: ')) {
            try {
              const d = JSON.parse(line.slice(6));
              handleStreamData(d);
            } catch(e) {}
          }
        });
        read();
      });
    }
    read();
  }).catch(err => setLog('❌ ' + err.message));
}

function handleStreamData(d) {
  if (d.log) {
    appendLog(d.log);
    const match = d.log.match(/frame=\s*(\d+)/);
    if (match) {
      const frame = parseInt(match[1]);
      const totalFrames = Math.round((fileInfo.duration || 8) * (fileInfo.fps || 24) * 450);
      const pct = Math.min(99, Math.round((frame / totalFrames) * 100));
      setProgress(pct, `⏳ Processing... frame ${frame}`);
    }
    if (d.log.includes('speed=')) {
      const speedMatch = d.log.match(/speed=(\S+)x/);
      if (speedMatch) setProgress(null, `⚡ Speed: ${speedMatch[1]}x realtime`);
    }
  }
  if (d.step) appendLog(`\n📦 Step ${d.step}/${d.total}: ${d.cmd}...`);
  if (d.status === 'done' || d.status === 'all_done') {
    setProgress(100, '✅ Selesai!');
    document.getElementById('btn-open-folder').classList.remove('hidden');
    if (d.output) appendLog(`\n✅ Output: ${d.output}`);
    if (d.thumbnail) appendLog(`🖼️ Thumbnail: ${d.thumbnail}`);
  }
  if (d.status === 'error') {
    setProgress(0, '❌ Error! Lihat log di bawah.');
  }
}

// ── OPEN FOLDER ──────────────────────────────────────────────
async function openFolder() {
  await fetch('/api/open-folder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ folder: lastOutputFolder })
  });
}

// ── LOG HELPERS ──────────────────────────────────────────────
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
  if (label) document.getElementById('progress-info').textContent = label;
}
