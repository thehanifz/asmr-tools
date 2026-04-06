/**
 * Panel Merge & Export — wired to HTML ids from index.html v2
 */
import { state } from "./state.js";
import { probeFile, browseVideo, browseAudio, mergeFiles, makeThumbnail } from "./api.js";
import { toast, log, clearLog, setProgress, setProgressIndeterminate,
         setPanelReady, setPanelProcessing, setPanelIdle } from "./ui.js";

const P = "merge";

export function initMergePanel() {
  // Auto-fill from video/audio ready events
  document.addEventListener("video:ready", (e) => {
    const el = document.getElementById("merge-video");
    if (el && e.detail?.path) el.value = e.detail.path;
  });
  document.addEventListener("audio:ready", (e) => {
    const el = document.getElementById("merge-audio");
    if (el && e.detail?.path) el.value = e.detail.path;
  });

  // Browse buttons (manual)
  document.getElementById("merge-video-browse")?.addEventListener("click", async () => {
    const res = await browseVideo();
    if (res?.path) document.getElementById("merge-video").value = res.path;
  });
  document.getElementById("merge-audio-browse")?.addEventListener("click", async () => {
    const res = await browseAudio();
    if (res?.path) document.getElementById("merge-audio").value = res.path;
  });

  // Auto-suggest merge output
  document.getElementById("merge-video")?.addEventListener("change", (e) => {
    const path = e.target.value;
    if (!path) return;
    const dir  = path.replace(/[\\/][^\\/]+$/, "");
    const base = path.split(/[\\/]/).pop().replace(/\.[^.]+$/, "");
    const outEl = document.getElementById("merge-output");
    if (outEl && !outEl.value) outEl.value = `${dir}\\${base}_final.mp4`;
  });

  // Merge run
  document.getElementById("merge-run")?.addEventListener("click", runMerge);

  // Thumbnail browse + run
  document.getElementById("thumb-video-browse")?.addEventListener("click", async () => {
    const res = await browseVideo();
    if (res?.path) {
      const el = document.getElementById("thumb-video");
      if (el) el.value = res.path;
      // Auto-suggest thumb output
      const dir  = res.path.replace(/[\\/][^\\/]+$/, "");
      const base = res.path.split(/[\\/]/).pop().replace(/\.[^.]+$/, "");
      const outEl = document.getElementById("thumb-output");
      if (outEl && !outEl.value) outEl.value = `${dir}\\${base}_thumbnail.jpg`;
    }
  });

  document.getElementById("thumb-run")?.addEventListener("click", runThumbnail);
}

async function runMerge() {
  const videoPath  = document.getElementById("merge-video")?.value.trim();
  const audioPath  = document.getElementById("merge-audio")?.value.trim();
  const outputPath = document.getElementById("merge-output")?.value.trim();

  if (!videoPath)  { toast("Pilih file video!", "error"); return; }
  if (!audioPath)  { toast("Pilih file audio!", "error"); return; }
  if (!outputPath) { toast("Isi path output!", "error"); return; }

  setPanelProcessing(P);
  clearLog(P);
  setProgress(P, 0);

  await mergeFiles({ video: videoPath, audio: audioPath, output: outputPath }, (ev) => {
    if (ev.log) {
      log(P, ev.log);
    } else if (ev.type === "done" || ev.status === "done") {
      setProgress(P, 100);
      log(P, `✅ Merge selesai — ${ev.size ?? ""} ${ev.elapsed ?? ""}`, "done");
      setPanelReady(P, outputPath.split(/[\\/]/).pop());
      toast("Merge selesai!", "success");
    } else if (ev.status === "error") {
      setPanelIdle(P);
      log(P, `❌ ${ev.message ?? "Merge error"}`, "error");
      toast("Merge gagal.", "error");
    }
  });
}

async function runThumbnail() {
  const videoPath  = document.getElementById("thumb-video")?.value.trim();
  const outputPath = document.getElementById("thumb-output")?.value.trim();
  const time       = parseFloat(document.getElementById("thumb-time")?.value ?? 5);

  if (!videoPath)  { toast("Pilih video untuk thumbnail!", "error"); return; }
  if (!outputPath) { toast("Isi path output thumbnail!", "error"); return; }

  log(P, "Generating thumbnail...");
  const res = await makeThumbnail({ input: videoPath, output: outputPath, time_sec: time });

  if (res.error) {
    log(P, `❌ ${res.error}`, "error");
    toast("Thumbnail gagal.", "error");
    return;
  }

  log(P, `🖼️ Thumbnail saved: ${outputPath}`, "done");
  toast("Thumbnail berhasil!", "success");

  // Show preview via blob URL from server static
  const preview = document.getElementById("thumb-preview");
  const wrap    = document.getElementById("thumb-preview-wrap");
  if (preview && wrap) {
    // request image from /api/thumbnail/preview?path=...
    preview.src = `/api/thumbnail/preview?path=${encodeURIComponent(outputPath)}&t=${Date.now()}`;
    wrap.style.display = "block";
  }
}
