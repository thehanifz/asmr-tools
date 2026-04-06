/**
 * Panel Video — handles all logic for the Video panel.
 * Responsibilities: file input, probe, crop/upscale/loop settings, process.
 */
import { state, emit } from "./state.js";
import { probeFile, browseVideo, processVideo } from "./api.js";
import { toast, log, clearLog, setStatus, setProgress, setPanelReady, setPanelProcessing, setPanelIdle } from "./ui.js";

const PANEL_ID = "panel-video";

export function initVideoPanel() {
  // Browse button
  document.getElementById("btn-browse-video")?.addEventListener("click", async () => {
    const res = await browseVideo();
    if (res.path) loadVideoFile(res.path);
  });

  // Manual path input + Load button
  document.getElementById("btn-load-video")?.addEventListener("click", () => {
    const path = document.getElementById("video-path")?.value.trim();
    if (path) loadVideoFile(path);
  });

  // Drag & drop
  const dropZone = document.getElementById("video-drop-zone");
  dropZone?.addEventListener("dragover", (e) => e.preventDefault());
  dropZone?.addEventListener("drop", (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) loadVideoFile(file.path ?? file.name);
  });

  // Process button
  document.getElementById("btn-process-video")?.addEventListener("click", runVideoPipeline);
}

async function loadVideoFile(path) {
  state.video.inputPath = path;
  document.getElementById("video-path").value = path;
  setStatus("Probing video...");
  const info = await probeFile(path);
  if (info.error) {
    toast(info.error, "error");
    return;
  }
  state.video.info = info;
  renderVideoInfo(info);
  // Auto-fill output folder if not set
  if (!state.output.folder) {
    const dir = path.substring(0, Math.max(path.lastIndexOf("\\"), path.lastIndexOf("/")));
    state.output.folder = dir;
    const folderInput = document.getElementById("output-folder");
    if (folderInput) folderInput.value = dir;
  }
  setStatus("Video loaded.");
}

function renderVideoInfo(info) {
  const box = document.getElementById("video-info");
  if (!box) return;
  box.classList.remove("hidden");
  box.innerHTML = `
    <table>
      <tr><td>File</td><td>${info.filename}</td></tr>
      <tr><td>Resolusi</td><td>${info.resolution ?? "-"}</td></tr>
      <tr><td>Durasi</td><td>${info.duration_str}</td></tr>
      <tr><td>FPS</td><td>${info.fps ?? "-"}</td></tr>
      <tr><td>Ukuran</td><td>${info.size_str}</td></tr>
    </table>
  `;
}

async function runVideoPipeline() {
  const { inputPath, info } = state.video;
  if (!inputPath) { toast("Pilih video dulu!", "error"); return; }
  const outputDir = state.output.folder || document.getElementById("output-folder")?.value.trim();
  if (!outputDir) { toast("Set output folder dulu!", "error"); return; }

  const cropPx = parseInt(document.getElementById("video-crop-px")?.value ?? 50);
  const doUpscale = document.getElementById("video-upscale")?.checked ?? true;
  const duration = parseInt(document.getElementById("target-duration")?.value ?? 3600);

  setPanelProcessing(PANEL_ID);
  clearLog();
  setProgress(0);

  let totalSteps = 1;
  let currentStep = 0;

  await processVideo(
    {
      input: inputPath,
      output_dir: outputDir,
      crop_px: cropPx,
      upscale: doUpscale,
      duration,
      video_duration: info?.duration ?? 8,
    },
    (event) => {
      if (event.type === "pipeline_start") {
        totalSteps = event.total_steps;
      } else if (event.type === "step_start") {
        currentStep = event.step;
        setStatus(`[${event.step}/${totalSteps}] ${event.label}`);
        setProgress(Math.round(((event.step - 1) / totalSteps) * 100));
      } else if (event.type === "step_done") {
        log(`✅ ${event.label} — ${event.elapsed} (${event.output_size})`, "success");
        setProgress(Math.round((event.step / totalSteps) * 100));
      } else if (event.log) {
        log(event.log);
      } else if (event.status === "all_done") {
        state.video.outputPath = event.output;
        state.video.ready = true;
        setProgress(100);
        setStatus("✅ Video selesai!");
        setPanelReady(PANEL_ID, event.output.split(/[\\/]/).pop());
        toast("Video selesai diproses!", "success");
        emit("video:ready", { path: event.output });
      } else if (event.status === "error" || event.type === "step_error") {
        setPanelIdle(PANEL_ID);
        setStatus("❌ Error saat proses video");
        toast("Proses video gagal.", "error");
      }
    }
  );
}
