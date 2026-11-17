// ═══════════════════════════════════════════════════════════════
//  Sound Picker — dropdown Pustaka Suara dengan preview + pilih
//  - Klik baris file  : putar/jeda preview suara (satu audio global)
//  - Tombol ">"       : pilih suara (callback onSelect), panel menutup
//  - Header kategori  : expand/collapse per kategori
//  Panel diposisikan fixed (lolos dari .workspace yang overflow-y:auto)
// ═══════════════════════════════════════════════════════════════

// ── Preview audio bersama: hanya satu suara yang berbunyi ─────
const previewAudio = new Audio();
previewAudio.preload = 'none';
let playingRow = null;   // .sp-item yang sedang berbunyi
let openPicker = null;   // picker yang panelnya sedang terbuka

function fmtDur(sec) {
  sec = Math.round(sec || 0);
  return Math.floor(sec / 60) + ':' + String(sec % 60).padStart(2, '0');
}

function stopPreview() {
  previewAudio.pause();
  previewAudio.removeAttribute('src');
  previewAudio.load();
  if (playingRow) {
    playingRow.classList.remove('playing');
    const btn = playingRow.querySelector('.sp-item-play');
    if (btn) btn.textContent = '▶';
    playingRow = null;
  }
}

previewAudio.addEventListener('ended', stopPreview);
previewAudio.addEventListener('error', stopPreview);

function el(tag, className, text) {
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (text !== undefined) n.textContent = text;
  return n;
}

export function createSoundPicker({ id, placeholder, onSelect }) {
  const root = el('div', 'sp-root');
  if (id) root.id = id;

  const trigger = el('button', 'input sp-trigger');
  trigger.type = 'button';
  trigger.disabled = true;
  const triggerLabel = el('span', 'sp-trigger-label', '🎧 Memuat Pustaka Suara…');
  const triggerChevron = el('span', 'sp-trigger-chevron', '▾');
  trigger.append(triggerLabel, triggerChevron);
  root.appendChild(trigger);

  let groups = [];
  let panel = null;

  // ── Panel ──────────────────────────────────────────────────
  function buildPanel() {
    panel = el('div', 'sp-panel');
    panel.setAttribute('role', 'listbox');

    // Tools: buka/tutup semua + hitungan
    const tools = el('div', 'sp-panel-tools');
    const expandAll = el('button', 'sp-tool-btn', 'Buka semua');
    expandAll.type = 'button';
    const collapseAll = el('button', 'sp-tool-btn', 'Tutup semua');
    collapseAll.type = 'button';
    const count = el('span', 'sp-count');
    const total = groups.reduce((n, g) => n + g.items.length, 0);
    count.textContent = `${total} suara · ${groups.length} kategori`;
    expandAll.addEventListener('click', () => setAllGroups(true));
    collapseAll.addEventListener('click', () => setAllGroups(false));
    tools.append(expandAll, collapseAll, count);
    panel.appendChild(tools);

    const list = el('div', 'sp-groups');
    if (groups.length === 0) {
      list.appendChild(el('div', 'sp-empty', 'Pustaka Suara kosong.'));
    }
    groups.forEach((g, gi) => {
      const group = el('div', 'sp-group');
      if (gi !== 0) group.classList.add('collapsed');

      const header = el('button', 'sp-group-header');
      header.type = 'button';
      header.setAttribute('aria-expanded', gi === 0 ? 'true' : 'false');
      const chev = el('span', 'sp-chevron', '▾');
      const lbl = el('span', 'sp-group-label', g.label);
      const cnt = el('span', 'sp-group-count', String(g.items.length));
      header.append(chev, lbl, cnt);
      header.addEventListener('click', () => {
        const collapsed = group.classList.toggle('collapsed');
        header.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      });
      group.appendChild(header);

      const items = el('div', 'sp-group-items');
      g.items.forEach((it) => {
        const row = el('div', 'sp-item');
        row.setAttribute('role', 'option');

        const playBtn = el('button', 'sp-item-play', '▶');
        playBtn.type = 'button';
        playBtn.title = 'Preview suara';
        const name = el('span', 'sp-item-name', it.name);
        name.title = it.path;
        const dur = el('span', 'sp-item-dur', fmtDur(it.duration));
        const selBtn = el('button', 'sp-item-select', '›');
        selBtn.type = 'button';
        selBtn.title = 'Pilih suara ini';
        row.append(playBtn, name, dur, selBtn);

        // Klik baris (di luar tombol pilih) = preview
        row.addEventListener('click', (e) => {
          if (e.target.closest('.sp-item-select')) return;
          togglePreview(row, it.path);
        });
        // Tombol ">" = pilih
        selBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          close();
          onSelect({ path: it.path, name: it.name, duration: it.duration || 0 });
        });
        items.appendChild(row);
      });
      group.appendChild(items);
      list.appendChild(group);
    });
    panel.appendChild(list);
    return panel;
  }

  function setAllGroups(expand) {
    if (!panel) return;
    panel.querySelectorAll('.sp-group').forEach((g) => {
      g.classList.toggle('collapsed', !expand);
      g.querySelector('.sp-group-header')
        ?.setAttribute('aria-expanded', expand ? 'true' : 'false');
    });
  }

  function togglePreview(row, path) {
    // Klik file yang sedang bunyi = jeda; klik file lain = pindah
    if (playingRow === row && !previewAudio.paused) {
      previewAudio.pause();
      row.classList.remove('playing');
      row.querySelector('.sp-item-play').textContent = '▶';
      playingRow = null;
      return;
    }
    if (playingRow === row && previewAudio.paused && previewAudio.src) {
      previewAudio.play().catch(() => {});
      row.classList.add('playing');
      row.querySelector('.sp-item-play').textContent = '❚❚';
      return;
    }
    stopPreview();
    playingRow = row;
    row.classList.add('playing');
    row.querySelector('.sp-item-play').textContent = '❚❚';
    previewAudio.src = `/api/library/play?path=${encodeURIComponent(path)}`;
    previewAudio.play().catch(() => stopPreview());
  }

  function positionPanel() {
    const r = trigger.getBoundingClientRect();
    const maxH = Math.min(420, Math.floor(window.innerHeight * 0.62));
    panel.style.maxHeight = maxH + 'px';
    panel.style.width = Math.max(r.width, 280) + 'px';
    panel.style.left = Math.max(8, Math.min(r.left, window.innerWidth - Math.max(r.width, 280) - 8)) + 'px';
    const spaceBelow = window.innerHeight - r.bottom;
    const spaceAbove = r.top;
    if (spaceBelow >= 240 || spaceBelow >= spaceAbove) {
      panel.style.top = (r.bottom + 4) + 'px';
      panel.style.bottom = 'auto';
    } else {
      panel.style.bottom = (window.innerHeight - r.top + 4) + 'px';
      panel.style.top = 'auto';
    }
  }

  function onDocPointerDown(e) {
    if (panel && !panel.contains(e.target) && !root.contains(e.target)) close();
  }
  function onKeyDown(e) {
    if (e.key === 'Escape') close();
  }
  function onScroll(e) {
    if (panel && panel.contains(e.target)) return;
    close();
  }

  function open() {
    if (openPicker && openPicker !== api) openPicker.close();
    if (!panel) buildPanel();
    document.body.appendChild(panel);
    positionPanel();
    openPicker = api;
    triggerChevron.textContent = '▴';
    document.addEventListener('pointerdown', onDocPointerDown, true);
    document.addEventListener('keydown', onKeyDown);
    window.addEventListener('resize', close);
    window.addEventListener('scroll', onScroll, true);
  }

  function close() {
    if (panel && panel.parentNode) panel.remove();
    stopPreview();
    if (openPicker === api) openPicker = null;
    triggerChevron.textContent = '▾';
    document.removeEventListener('pointerdown', onDocPointerDown, true);
    document.removeEventListener('keydown', onKeyDown);
    window.removeEventListener('resize', close);
    window.removeEventListener('scroll', onScroll, true);
  }

  trigger.addEventListener('click', () => {
    if (panel && panel.parentNode) close();
    else open();
  });

  // ── API publik ─────────────────────────────────────────────
  const api = {
    root,
    close,
    setGroups(next) {
      groups = next || [];
      panel = null; // dibangun ulang saat dibuka
      trigger.disabled = false;
      triggerLabel.textContent = placeholder || '🎧 Pilih dari Pustaka Suara…';
    },
    setError() {
      trigger.disabled = true;
      triggerLabel.textContent = '🎧 Pustaka Suara tidak tersedia';
    },
  };
  return api;
}
