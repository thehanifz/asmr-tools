// Audio Loop tab logic
// Dipanggil dari index.html saat tab audio aktif

function initAudioLoopTab() {
  // Update label durasi
  const durInput = document.getElementById('audio-loop-duration');
  if (durInput) {
    durInput.addEventListener('input', updateAudioDurationLabel);
    updateAudioDurationLabel();
  }

  // Update output extension saat format berubah
  document.querySelectorAll('input[name="audio-loop-fmt"]').forEach(radio => {
    radio.addEventListener('change', updateAudioOutputExt);
  });
}

function updateAudioDurationLabel() {
  const sec = parseInt(document.getElementById('audio-loop-duration').value) || 0;
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const el = document.getElementById('audio-duration-label');
  if (el) el.textContent = `= ${h} jam ${m} menit`;
}

function updateAudioOutputExt() {
  const fmt = document.querySelector('input[name="audio-loop-fmt"]:checked')?.value || 'mp3';
  const extMap = { mp3: '.mp3', aac: '.m4a', flac: '.flac', wav: '.wav' };
  const outputEl = document.getElementById('audio-output');
  if (!outputEl || !outputEl.value) return;
  // Ganti ekstensi
  const base = outputEl.value.replace(/\.[^.]+$/, '');
  outputEl.value = base + (extMap[fmt] || '.mp3');
}

async function runAudioLoop() {
  const inputPath  = document.getElementById('audio-file').value.trim();
  const outputPath = document.getElementById('audio-output').value.trim();
  const duration   = parseInt(document.getElementById('audio-loop-duration').value) || 3600;
  const xfade      = parseFloat(document.getElementById('audio-xfade').value) || 1.0;
  const fmt        = document.querySelector('input[name="audio-loop-fmt"]:checked')?.value || 'mp3';
  const workspace  = document.getElementById('workspace-dir').value.trim();

  if (!inputPath) { alert('Pilih file audio terlebih dahulu!'); return; }

  // Derive output path jika kosong
  let finalOutput = outputPath;
  if (!finalOutput) {
    const extMap  = { mp3: '.mp3', aac: '.m4a', flac: '.flac', wav: '.wav' };
    const sep     = os_sep();
    const dir     = workspace || (inputPath.includes(sep)
      ? inputPath.substring(0, inputPath.lastIndexOf(sep))
      : inputPath.substring(0, inputPath.lastIndexOf('/')));
    const base    = inputPath.split(sep).pop().split('/').pop().replace(/\.[^.]+$/, '');
    finalOutput   = `${dir}${sep}${base}_loop${extMap[fmt] || '.mp3'}`;
    document.getElementById('audio-output').value = finalOutput;
  }

  startStream('/api/audio/loop', {
    input: inputPath,
    output: finalOutput,
    duration,
    xfade,
    format: fmt,
  });
}
