// ═══════════════════════════════════════════════
//  Jobs — daftar render yang bisa dilanjutkan
//  Render berjalan terlepas dari tab browser; bila service dimulai ulang,
//  job yang terhenti ditandai "interrupted" dan bisa dilanjutkan dari
//  checkpoint terakhir via tombol Lanjutkan.
// ═══════════════════════════════════════════════
import { toast } from './ui.js';

const TYPE_PANEL = {
  'sound-layer': 'sound-layer',
  'video-pipeline': 'video',
  'loop-ba': 'loop-ba',
  'audio-loop': null, // tidak ada panel audio-loop; hanya tampil di daftar Jobs
};
const RESUMABLE = new Set(['interrupted', 'error', 'cancelled']);
const ACTIVE = new Set(['running', 'queued']);
const STATUS_LABEL = {
  queued: 'Antre',
  running: 'Berjalan',
  interrupted: 'Terhenti',
  done: 'Selesai',
  error: 'Error',
  cancelled: 'Dibatalkan',
};

let jobsCache = [];
let logOpenId = null;

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function fmtTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString('id-ID', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export function initJobs() {
  document.getElementById('btnJobsRefresh')?.addEventListener('click', () => refreshJobs(true));
  document.addEventListener('click', onJobActionClick);
  refreshJobs(false);
  setInterval(() => refreshJobs(false), 4000);
}

async function refreshJobs(manual) {
  try {
    const res = await fetch('/api/jobs');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    jobsCache = data.jobs || [];
  } catch (err) {
    if (manual) toast('Gagal memuat jobs: ' + err.message, 'error');
    if (!jobsCache.length) {
      const list = document.getElementById('jobsList');
      if (list) list.innerHTML = '<div class="jobs-empty">Gagal memuat daftar job.</div>';
    }
    return;
  }
  renderJobsList();
  renderPanelBanners();
  renderNavBadge();
}

function renderJobsList() {
  const list = document.getElementById('jobsList');
  if (!list) return;
  if (!jobsCache.length) {
    list.innerHTML = '<div class="jobs-empty">Belum ada job. Render dari panel Sound Layer, Video Loop, atau Loop B+A akan tercatat di sini dan bisa dilanjutkan bila terhenti.</div>';
    return;
  }
  list.innerHTML = jobsCache.map(job => {
    const status = job.status;
    const pct = Math.max(0, Math.min(100, job.progress || 0));
    const seg = job.segments_total ? ` · ${job.segments_done_count}/${job.segments_total} segmen` : '';
    const actions = [];
    if (RESUMABLE.has(status)) {
      actions.push(`<button class="btn btn-primary btn-job" data-job-action="resume" data-job-id="${esc(job.id)}">▶ Lanjutkan</button>`);
    }
    if (status === 'running' || status === 'queued') {
      actions.push(`<button class="btn btn-secondary btn-job" data-job-action="cancel" data-job-id="${esc(job.id)}">Batalkan</button>`);
    }
    if (status !== 'running' && status !== 'queued') {
      actions.push(`<button class="btn btn-ghost btn-job" data-job-action="delete" data-job-id="${esc(job.id)}">Hapus</button>`);
    }
    actions.push(`<button class="btn btn-ghost btn-job" data-job-action="log" data-job-id="${esc(job.id)}">${logOpenId === job.id ? 'Tutup Log' : 'Log'}</button>`);
    return `<div class="job-card">
      <div class="job-card-top">
        <div class="job-card-main">
          <span class="job-status st-${esc(status)}">${esc(STATUS_LABEL[status] || status)}</span>
          <span class="job-label">${esc(job.label || job.id)}</span>
          <span class="job-type">${esc(job.type_label || job.type || '')}</span>
        </div>
        <span class="job-time">${esc(fmtTime(job.created_at))}</span>
      </div>
      <div class="job-progress"><div class="job-progress-fill st-${esc(status)}" style="width:${pct}%"></div></div>
      <div class="job-meta">
        <span>${pct}%${esc(seg)}</span>
        ${job.output_path ? `<span class="job-output" title="${esc(job.output_path)}">${esc(job.output_path)}</span>` : ''}
      </div>
      ${job.error ? `<div class="job-error">✗ ${esc(job.error)}</div>` : ''}
      ${job.last_log && status !== 'done' ? `<div class="job-lastlog">${esc(job.last_log)}</div>` : ''}
      <div class="job-actions">${actions.join('')}</div>
      ${logOpenId === job.id ? `<div class="job-log" id="jobLog-${esc(job.id)}">Memuat log...</div>` : ''}
    </div>`;
  }).join('');
  if (logOpenId) fillJobLog(logOpenId);
}

async function fillJobLog(jobId) {
  const box = document.getElementById('jobLog-' + jobId);
  if (!box) return;
  try {
    const res = await fetch('/api/jobs/' + encodeURIComponent(jobId));
    const job = await res.json();
    const lines = (job.events || []).map(e => {
      if (e.log) return `[${e.ts || ''}] ${e.log}`;
      if (e.type === 'step_start') return `▶ ${e.label || ''}`;
      if (e.type === 'step_done') return `✓ ${e.label || ''} — ${e.elapsed || ''} · ${e.output_size || ''}`;
      if (e.status === 'done' || e.status === 'all_done') return `✓ Selesai: ${e.output || ''}`;
      return '';
    }).filter(Boolean);
    box.textContent = lines.slice(-60).join('\n') || '(log kosong)';
  } catch (err) {
    box.textContent = 'Gagal memuat log: ' + err.message;
  }
}

function renderPanelBanners() {
  const byPanel = {};
  for (const job of jobsCache) {
    if (!RESUMABLE.has(job.status)) continue;
    const panel = TYPE_PANEL[job.type];
    if (!panel) continue;
    (byPanel[panel] = byPanel[panel] || []).push(job);
  }
  for (const panel of new Set(Object.values(TYPE_PANEL))) {
    if (!panel) continue;
    const section = document.getElementById('tool-' + panel);
    if (!section) continue;
    const bannerId = 'jobsBanner-' + panel;
    let banner = document.getElementById(bannerId);
    const jobs = byPanel[panel] || [];
    if (!jobs.length) {
      banner?.remove();
      continue;
    }
    if (!banner) {
      banner = document.createElement('div');
      banner.id = bannerId;
      banner.className = 'jobs-banner';
      const header = section.querySelector('.tool-header');
      if (header) header.after(banner);
      else section.prepend(banner);
    }
    banner.innerHTML = `<span class="jobs-banner-text">⚠️ ${jobs.length} job terhenti dari panel ini.</span>` +
      jobs.map(j => `<button class="btn btn-primary btn-job" data-job-action="resume" data-job-id="${esc(j.id)}">▶ Lanjutkan: ${esc(j.label || j.id)}</button>`).join('') +
      `<button class="btn btn-ghost btn-job" data-job-action="goto-jobs">Lihat Jobs</button>`;
  }
}

function renderNavBadge() {
  const badge = document.getElementById('jobsBadge');
  if (!badge) return;
  // Lencana Jobs = jumlah job yang SEDANG berjalan/antre. Job yang
  // terhenti (bisa dilanjutkan) disorot lewat banner panel dan panel
  // Jobs itu sendiri, bukan dihitung di sini.
  const n = jobsCache.filter(j => ACTIVE.has(j.status)).length;
  badge.textContent = String(n);
  badge.classList.toggle('hidden', n === 0);
}

async function onJobActionClick(e) {
  const btn = e.target.closest('[data-job-action]');
  if (!btn) return;
  const action = btn.dataset.jobAction;
  const id = btn.dataset.jobId;

  if (action === 'goto-jobs') {
    document.querySelector('.nav-item[data-tool="jobs"]')?.click();
    return;
  }
  if (action === 'log') {
    logOpenId = logOpenId === id ? null : id;
    renderJobsList();
    return;
  }
  if (action === 'resume') {
    btn.disabled = true;
    try {
      const res = await fetch(`/api/jobs/${encodeURIComponent(id)}/resume`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) toast(data.error || 'Gagal melanjutkan job', 'error');
      else toast('Job dilanjutkan dari checkpoint terakhir.', 'success');
    } catch (err) {
      toast('Error: ' + err.message, 'error');
    }
    refreshJobs(false);
    return;
  }
  if (action === 'cancel') {
    if (!confirm('Batalkan job ini? Segmen yang sudah selesai tetap tersimpan dan job bisa dilanjutkan lagi.')) return;
    try {
      const res = await fetch(`/api/jobs/${encodeURIComponent(id)}/cancel`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) toast(data.error || 'Gagal membatalkan job', 'error');
      else toast('Job dibatalkan.', 'success');
    } catch (err) {
      toast('Error: ' + err.message, 'error');
    }
    refreshJobs(false);
    return;
  }
  if (action === 'delete') {
    if (!confirm('Hapus job ini beserta segmen/checkpoint-nya? Output akhir (bila sudah ada) tidak dihapus.')) return;
    try {
      const res = await fetch(`/api/jobs/${encodeURIComponent(id)}`, { method: 'DELETE' });
      const data = await res.json();
      if (!res.ok) toast(data.error || 'Gagal menghapus job', 'error');
      else toast('Job dihapus.', 'success');
    } catch (err) {
      toast('Error: ' + err.message, 'error');
    }
    if (logOpenId === id) logOpenId = null;
    refreshJobs(false);
    return;
  }
}
