/**
 * Enhanced SSE Log Handler dengan Timestamp + Elapsed Timer + Heartbeat Status
 * Auto-attach ke semua fungsi yang pakai EventSource di index.html
 */

// Helper: format elapsed seconds
function fmtElapsed(sec) {
  if (!sec) return '0s';
  const s = Math.floor(sec);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}m ${rem.toString().padStart(2, '0')}s`;
}

// Enhanced log function — tambahkan ke window global
window.enhancedLog = function(logBox, statusEl, data) {
  const ts = data.ts || new Date().toLocaleTimeString('id-ID', {hour12: false});
  const elapsed = data.elapsed !== undefined ? fmtElapsed(data.elapsed) : '';
  const prefix = `[${ts}]${elapsed ? ' (' + elapsed + ')' : ''}`;

  if (data.log) {
    // FFmpeg log line biasa
    logBox.textContent += `${prefix} ${data.log}\n`;
  } else if (data.status === 'start') {
    // Proses mulai
    logBox.textContent += `${prefix} ▶️ Memulai proses${data.label ? ': ' + data.label : ''}...\n`;
    if (statusEl) statusEl.textContent = '🔄 Running · 0s';
  } else if (data.status === 'ping') {
    // Heartbeat — update status saja, tidak tambah log line
    if (statusEl) statusEl.textContent = `🔄 Running · ${elapsed}`;
  } else if (data.status === 'done') {
    // Sukses
    logBox.textContent += `${prefix} ✅ Proses selesai (${data.code === 0 ? 'OK' : 'code: ' + data.code})\n`;
    if (statusEl) statusEl.textContent = `✅ Done · ${elapsed}`;
  } else if (data.status === 'error') {
    // Error
    logBox.textContent += `${prefix} ❌ Error (code: ${data.code})\n`;
    if (statusEl) statusEl.textContent = `❌ Error · ${elapsed}`;
  }

  logBox.scrollTop = logBox.scrollHeight;
};

// Wrapper SSE runner universal
window.runSSE = async function(url, payload, logBox, statusEl, onDone) {
  if (!logBox) {
    console.error('runSSE: logBox element tidak ditemukan');
    return;
  }

  logBox.textContent = '';
  if (statusEl) statusEl.textContent = '🔄 Starting...';

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errText = await res.text();
      logBox.textContent += `[ERROR] HTTP ${res.status}: ${errText}\n`;
      if (statusEl) statusEl.textContent = '❌ HTTP Error';
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, {stream: true});
      const lines = buffer.split('\n');
      buffer = lines.pop(); // sisa incomplete line

      for (const line of lines) {
        if (!line.trim() || !line.startsWith('data: ')) continue;
        const jsonStr = line.substring(6); // setelah "data: "
        try {
          const data = JSON.parse(jsonStr);
          window.enhancedLog(logBox, statusEl, data);

          // Trigger callback jika done/error
          if ((data.status === 'done' || data.status === 'error') && onDone) {
            setTimeout(() => onDone(data), 100);
          }
        } catch (e) {
          // JSON parse error — abaikan line rusak
          console.warn('SSE parse error:', jsonStr, e);
        }
      }
    }
  } catch (e) {
    logBox.textContent += `[ERROR] ${e.message}\n`;
    if (statusEl) statusEl.textContent = '❌ Connection Error';
    console.error('runSSE error:', e);
  }
};

console.log('✅ log-handler.js loaded — window.runSSE dan window.enhancedLog tersedia');
