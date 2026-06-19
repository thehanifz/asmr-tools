// ═══════════════════════════════════════════════
//  Panel: Live to YouTube (ASMR Loop Streamer)
// ═══════════════════════════════════════════════
import { AppState, setWorkspace } from './state.js';
import { browseVideo, browseAudio, probeFile } from './api.js';
import { toast, showFileInfo } from './ui.js';

export function initLive() {
  const $ = id => document.getElementById(id);

  let selectedVideoPath = "";
  let selectedVideoSource = "local"; // local or library
  let selectedAudioPath = "";
  let selectedAudioSource = "video"; // video, library, mute
  let activeEventSource = null;
  let videoHeight = 0;

  // ── Collapsible Log Box ────────────────────────────────
  function initCollapsible(toggleId, bodyId) {
    const toggle = $(toggleId);
    const body   = $(bodyId);
    if (!toggle || !body) return;
    toggle.addEventListener('click', () => {
      const isOpen = body.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(isOpen));
    });
  }
  initCollapsible('toggleLiveLog', 'liveLogBody');

  // ── Toggle Stream Key Visibility ────────────────────────
  $('btnLiveToggleKey')?.addEventListener('click', () => {
    const input = $('liveStreamKey');
    const btn = $('btnLiveToggleKey');
    if (input.type === 'password') {
      input.type = 'text';
      btn.textContent = '🙈';
    } else {
      input.type = 'password';
      btn.textContent = '👁️';
    }
  });

  // ── Toggle Input Source Panels ──────────────────────────
  document.querySelectorAll('input[name="liveVideoSource"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
      selectedVideoSource = e.target.value;
      if (selectedVideoSource === 'local') {
        $('liveVideoLocalRow').classList.remove('hidden');
        $('liveVideoLibraryRow').classList.add('hidden');
        _updateSelectedVideoInfo(selectedVideoPath, false);
      } else {
        $('liveVideoLocalRow').classList.add('hidden');
        $('liveVideoLibraryRow').classList.remove('hidden');
        _loadVideoLibrary();
      }
    });
  });

  document.querySelectorAll('input[name="liveAudioSource"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
      selectedAudioSource = e.target.value;
      if (selectedAudioSource === 'library') {
        $('liveAudioLibraryRow').classList.remove('hidden');
        _loadAudioLibrary();
      } else {
        $('liveAudioLibraryRow').classList.add('hidden');
      }
    });
  });

  // ── Browse Local Video ────────────────────────────────
  $('btnLiveBrowseVideo')?.addEventListener('click', async () => {
    const path = await browseVideo();
    if (!path) return;
    $('liveVideoLocalInput').value = path;
    setWorkspace(path);
    selectedVideoPath = path;
    
    // Probe resolution
    const info = await probeFile(path);
    if (info.error) {
      toast(info.error, 'error');
      return;
    }
    videoHeight = info.height || 0;
    _updateSelectedVideoInfo(path, true, info);
  });

  // ── Upload Video / Audio to Library ─────────────────────
  $('btnLiveUploadVideo')?.addEventListener('click', () => {
    $('liveVideoUploadFileInput').click();
  });

  $('liveVideoUploadFileInput')?.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    toast('Mengunggah video ke library...', 'info');
    try {
      const res = await fetch('/api/live/library/video/add', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.status === 'success') {
        toast('Video berhasil ditambahkan ke library!', 'success');
        _loadVideoLibrary();
      } else {
        toast('Upload video gagal: ' + (data.error || 'Unknown error'), 'error');
      }
    } catch (err) {
      toast('Upload video error: ' + err.message, 'error');
    }
    // Reset file input
    e.target.value = '';
  });

  $('btnLiveUploadAudio')?.addEventListener('click', () => {
    $('liveAudioUploadFileInput').click();
  });

  $('liveAudioUploadFileInput')?.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    toast('Mengunggah audio ke library...', 'info');
    try {
      const res = await fetch('/api/live/library/audio/add', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.status === 'success') {
        toast('Audio berhasil ditambahkan ke library!', 'success');
        _loadAudioLibrary();
      } else {
        toast('Upload audio gagal: ' + (data.error || 'Unknown error'), 'error');
      }
    } catch (err) {
      toast('Upload audio error: ' + err.message, 'error');
    }
    e.target.value = '';
  });

  // ── Fetch and Render Video Library ─────────────────────
  async function _loadVideoLibrary() {
    const listEl = $('liveVideoLibraryList');
    if (!listEl) return;
    
    listEl.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:16px; color:var(--text-muted);">Memuat pustaka...</div>';
    
    try {
      const res = await fetch('/api/live/library/video');
      const items = await res.json();
      
      if (!items || items.length === 0) {
        listEl.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:16px; color:var(--text-muted); font-size:12px; border:1px dashed var(--border); border-radius:8px;">Pustaka video kosong. Silakan upload berkas baru.</div>';
        return;
      }
      
      listEl.innerHTML = '';
      items.forEach(item => {
        const div = document.createElement('div');
        div.className = 'library-item';
        if (selectedVideoSource === 'library' && selectedVideoPath === item.filename) {
          div.className += ' selected';
        }
        
        // Render thumbnail
        const thumbUrl = item.thumbnail ? `/${item.thumbnail}?t=${Date.now()}` : '';
        const thumbHTML = thumbUrl 
          ? `<img src="${thumbUrl}" class="library-thumb" alt="thumb">`
          : `<div class="library-icon">📹</div>`;
          
        div.innerHTML = `
          ${thumbHTML}
          <div class="library-info">
            <div class="library-name" title="${item.filename}">${item.title}</div>
            <div class="library-meta">${item.width}x${item.height} • ${item.size_str}</div>
          </div>
          <button class="library-delete-btn" title="Hapus" onclick="event.stopPropagation(); window.deleteLiveVideo('${item.filename}')">
            🗑️
          </button>
        `;
        
        div.addEventListener('click', () => {
          document.querySelectorAll('#liveVideoLibraryList .library-item').forEach(el => el.classList.remove('selected'));
          div.classList.add('selected');
          selectedVideoPath = item.filename;
          videoHeight = item.height || 0;
          _updateSelectedVideoInfo(item.filename, true, item);
        });
        
        listEl.appendChild(div);
      });
    } catch (err) {
      listEl.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:16px; color:#ef4444;">Gagal memuat: ${err.message}</div>`;
    }
  }

  // Exposed globally for delete buttons
  window.deleteLiveVideo = async (filename) => {
    if (!confirm(`Hapus video "${filename}" dari library?`)) return;
    try {
      const res = await fetch(`/api/live/library/video/${filename}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.status === 'success') {
        toast('Video terhapus', 'success');
        if (selectedVideoPath === filename) {
          selectedVideoPath = '';
          videoHeight = 0;
          $('liveVideoSelectedInfo').innerHTML = '';
        }
        _loadVideoLibrary();
      }
    } catch (err) {
      toast('Gagal menghapus video: ' + err.message, 'error');
    }
  };

  // ── Fetch and Render Audio Library ─────────────────────
  async function _loadAudioLibrary() {
    const listEl = $('liveAudioLibraryList');
    if (!listEl) return;
    
    listEl.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:16px; color:var(--text-muted);">Memuat pustaka...</div>';
    
    try {
      const res = await fetch('/api/live/library/audio');
      const items = await res.json();
      
      if (!items || items.length === 0) {
        listEl.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:16px; color:var(--text-muted); font-size:12px; border:1px dashed var(--border); border-radius:8px;">Pustaka audio kosong. Silakan upload berkas baru.</div>';
        return;
      }
      
      listEl.innerHTML = '';
      items.forEach(item => {
        const div = document.createElement('div');
        div.className = 'library-item';
        if (selectedAudioSource === 'library' && selectedAudioPath === item.filename) {
          div.className += ' selected';
        }
        
        div.innerHTML = `
          <div class="library-icon">🎵</div>
          <div class="library-info">
            <div class="library-name" title="${item.filename}">${item.title}</div>
            <div class="library-meta">${item.format.toUpperCase()} • ${item.size_str}</div>
          </div>
          <button class="library-delete-btn" title="Hapus" onclick="event.stopPropagation(); window.deleteLiveAudio('${item.filename}')">
            🗑️
          </button>
        `;
        
        div.addEventListener('click', () => {
          document.querySelectorAll('#liveAudioLibraryList .library-item').forEach(el => el.classList.remove('selected'));
          div.classList.add('selected');
          selectedAudioPath = item.filename;
          $('liveAudioSelectedInfo').innerHTML = `<span>✓ Dipilih: ${item.filename} (loop independen)</span>`;
          $('liveAudioSelectedInfo').classList.add('visible');
        });
        
        listEl.appendChild(div);
      });
    } catch (err) {
      listEl.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:16px; color:#ef4444;">Gagal memuat: ${err.message}</div>`;
    }
  }

  window.deleteLiveAudio = async (filename) => {
    if (!confirm(`Hapus audio "${filename}" dari library?`)) return;
    try {
      const res = await fetch(`/api/live/library/audio/${filename}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.status === 'success') {
        toast('Audio terhapus', 'success');
        if (selectedAudioPath === filename) {
          selectedAudioPath = '';
          $('liveAudioSelectedInfo').innerHTML = '';
        }
        _loadAudioLibrary();
      }
    } catch (err) {
      toast('Gagal menghapus audio: ' + err.message, 'error');
    }
  };

  // ── Sync UI with selected video details & quality dropdown ──────────
  function _updateSelectedVideoInfo(path, isLoaded, info = null) {
    const el = $('liveVideoSelectedInfo');
    if (!path) {
      el.innerHTML = '';
      el.classList.remove('visible');
      return;
    }
    
    if (isLoaded && info) {
      const parts = [];
      parts.push(info.filename || path);
      if (info.duration) {
        const s = parseInt(info.duration);
        const m = Math.floor(s / 60);
        const sec = s % 60;
        parts.push(`⏱ ${m}m ${sec}s`);
      }
      if (info.width && info.height) parts.push(`🖥 ${info.width}x${info.height}`);
      if (info.size_str) parts.push(`💾 ${info.size_str}`);
      
      el.innerHTML = parts.map(p => `<span>${p}</span>`).join(' · ');
      el.classList.add('visible');
    } else {
      el.innerHTML = `<span>✓ Dipilih: ${path}</span>`;
      el.classList.add('visible');
    }

    _updateQualityDropdown();
  }

  function _updateQualityDropdown() {
    const select = $('liveStreamQuality');
    if (!select) return;
    
    select.innerHTML = '';
    
    // Choose dynamic option based on source video resolution
    if (videoHeight >= 1080) {
      select.innerHTML = `
        <option value="1080p">1080p (8 Mbps)</option>
        <option value="720p" selected>720p (5 Mbps)</option>
        <option value="480p">480p (2.5 Mbps)</option>
      `;
    } else if (videoHeight >= 720) {
      select.innerHTML = `
        <option value="720p" selected>720p (5 Mbps)</option>
        <option value="480p">480p (2.5 Mbps)</option>
      `;
    } else {
      select.innerHTML = `
        <option value="480p" selected>480p (2.5 Mbps)</option>
        <option value="360p">360p (1 Mbps)</option>
      `;
    }
    
    _syncBandwidthWarning();
  }

  $('liveStreamQuality')?.addEventListener('change', _syncBandwidthWarning);

  function _syncBandwidthWarning() {
    const select = $('liveStreamQuality');
    const warning = $('liveBandwidthWarning');
    if (select && warning) {
      warning.style.display = select.value === '1080p' ? 'block' : 'none';
    }
  }

  // ── SSE Status listener ──────────────────────────────
  function startSSEStatusListener() {
    if (activeEventSource) {
      activeEventSource.close();
    }
    
    activeEventSource = new EventSource('/api/live/status/stream');
    
    activeEventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        _updateUIFromState(data);
      } catch (err) {
        console.error('SSE JSON error', err);
      }
    };
    
    activeEventSource.onerror = () => {
      console.warn('SSE connection disconnected. Re-connecting...');
    };
  }

  function _updateUIFromState(stateData) {
    const statusBar = $('liveStatusBar');
    const statusText = $('liveStatusText');
    const statusDot = $('liveStatusDot');
    const timerText = $('liveTimerText');
    const btnStart = $('btnLiveStart');
    const btnStop = $('btnLiveStop');
    const logBox = $('liveLog');
    
    // Sync class names
    statusBar.className = `status-bar-live ${stateData.status}`;
    
    // Sync text values
    if (stateData.status === 'idle') {
      statusText.textContent = 'Idle';
      statusDot.className = 'live-dot';
      btnStart.disabled = false;
      btnStop.disabled = true;
      btnStart.innerHTML = '🔴 Mulai Live';
    } else if (stateData.status === 'connecting') {
      statusText.textContent = 'Connecting...';
      statusDot.className = 'live-dot active';
      btnStart.disabled = true;
      btnStop.disabled = false;
      btnStart.innerHTML = '<span class="loading-spinner"></span> Connecting...';
    } else if (stateData.status === 'reconnecting') {
      statusText.textContent = `Reconnecting... (attempt #${stateData.reconnect_attempts})`;
      statusDot.className = 'live-dot active';
      btnStart.disabled = true;
      btnStop.disabled = false;
    } else if (stateData.status === 'live') {
      statusText.textContent = '🔴 LIVE';
      statusDot.className = 'live-dot active';
      btnStart.disabled = true;
      btnStop.disabled = false;
    } else if (stateData.status === 'error') {
      statusText.textContent = `Error: ${stateData.error_message || 'Stream failed'}`;
      statusDot.className = 'live-dot';
      btnStart.disabled = false;
      btnStop.disabled = true;
    }
    
    // Format duration
    const durSec = stateData.duration || 0;
    const h = Math.floor(durSec / 3600);
    const m = Math.floor((durSec % 3600) / 60);
    const s = durSec % 60;
    timerText.textContent = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    
    // Fill log output
    if (stateData.logs && stateData.logs.length > 0) {
      logBox.innerHTML = '';
      logBox.classList.add('visible');
      stateData.logs.forEach(line => {
        const div = document.createElement('div');
        div.className = 'log-line';
        if (line.includes('[Warning]') || line.includes('warning') || line.includes('Warning')) {
          div.className += ' warn';
        } else if (line.includes('Error') || line.includes('Gagal') || line.includes('gagal') || line.includes('failed')) {
          div.className += ' error';
        } else if (line.includes('LIVE') || line.includes('Memulai stream')) {
          div.className += ' done';
        }
        div.textContent = line;
        logBox.appendChild(div);
      });
      // Scroll logs to bottom
      logBox.scrollTop = logBox.scrollHeight;
    }
  }

  // ── Actions: Start Streaming ───────────────────────────
  $('btnLiveStart')?.addEventListener('click', async () => {
    if (!selectedVideoPath) {
      toast('Silakan pilih berkas video terlebih dahulu', 'error');
      return;
    }
    
    const streamKey = $('liveStreamKey').value.trim();
    if (!streamKey) {
      toast('Stream key YouTube tidak boleh kosong', 'error');
      return;
    }
    
    const payload = {
      video_source: selectedVideoSource,
      video_path: selectedVideoPath,
      audio_source: selectedAudioSource,
      audio_path: selectedAudioSource === 'library' ? selectedAudioPath : '',
      quality: $('liveStreamQuality').value,
      rtmp_url: $('liveRtmpUrl').value.trim(),
      stream_key: streamKey
    };
    
    $('btnLiveStart').disabled = true;
    $('btnLiveStart').innerHTML = '<span class="loading-spinner"></span> Memulai...';
    
    try {
      const res = await fetch('/api/live/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      const data = await res.json();
      if (res.ok) {
        toast('Proses live stream sedang diinisialisasi...', 'success');
        startSSEStatusListener();
      } else {
        toast(data.error || 'Gagal memulai streaming', 'error');
        $('btnLiveStart').disabled = false;
        $('btnLiveStart').innerHTML = '🔴 Mulai Live';
      }
    } catch (err) {
      toast('Error: ' + err.message, 'error');
      $('btnLiveStart').disabled = false;
      $('btnLiveStart').innerHTML = '🔴 Mulai Live';
    }
  });

  // ── Actions: Stop Streaming ────────────────────────────
  $('btnLiveStop')?.addEventListener('click', async () => {
    if (!confirm('Apakah Anda yakin ingin menghentikan live streaming?')) return;
    
    $('btnLiveStop').disabled = true;
    $('btnLiveStop').innerHTML = '<span class="loading-spinner"></span> Menghentikan...';
    
    try {
      const res = await fetch('/api/live/stop', { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        toast('Streaming berhasil dihentikan.', 'success');
        // Let SSE listener handle UI reset
      } else {
        toast(data.error || 'Gagal menghentikan streaming', 'error');
      }
    } catch (err) {
      toast('Error saat menghentikan streaming: ' + err.message, 'error');
    } finally {
      $('btnLiveStop').innerHTML = '⏹ Hentikan Live';
    }
  });

  // Start status listener on mount to recover UI state on page refresh
  startSSEStatusListener();
}
