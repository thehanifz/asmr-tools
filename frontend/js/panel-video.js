/**
 * Panel Video — wired to HTML ids from index.html v2
 */
import { state, emit } from "./state.js";
import { probeFile, browseVideo, processVideo } from "./api.js";
import { toast, log, clearLog, setProgress, setProgressIndeterminate,
         setPanelReady, setPanelProcessing, setPanelIdle, showProbe } from "./ui.js";

const P = "video";

export function initVideoPanel() {
  // Browse
  document.getElementById("video-browse")?.addEventListener("click", async () => {
    const res = await browseVideo();
    if (res?.path) await loadVideo(res.path);
  });

  // Run
  document.getElementById("video-run")?.addEventListener("click", runVideoPipeline);

  // Auto-suggest output path when input changes
  document.getElementById("video-path")?.addEventListener("change", (e) => {
    if (e.target.value) loadVideo(e.target.value);
  });
}

async function loadVideo(path) {
  state.video.inputPath = path;
  const el = document.getElementById("video-path");
  if (el) el.value = path;

  setPanelProcessing(P);
  const info = await probeFile(path);
  if (info.error) { toast(info.error, "error"); setPanelIdle(P); return; }

  state.video.info = info;
  renderVideoProbe(info);
  showProbe(P);

  // Auto-suggest output
  const dir = path.replace(/[\\/][^\\/]+$/, "");
  const base = path.split(/[\\/]/).pop().replace(/\.[^.]+$/, "");
  const outEl = document.getElementById("video-output");
  if (outEl && !outEl.value) outEl.value = `${dir}\\${base}_processed.mp4`;

  setPanelIdle(P);
}

function renderVideoProbe(info) {
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val ?? "—"; };
  set("v-res",     info.resolution);
  set("v-dur",     info.duration_str);
  set("v-fps",     info.fps ? `${info.fps} fps` : "—");
  set("v-codec",   info.video_codec);
  set("v-bitrate", info.bitrate_str);
  set("v-size",    info.size_str);
}

async function runVideoPipeline() {
  const inputPath = state.video.inputPath || document.getElementById("video-path")?.value.trim();
  if (!inputPath) { toast("Pilih file video dulu!", "error"); return; }

  const outputPath = document.getElementById("video-output")?.value.trim();
  if (!outputPath) { toast("Isi path output video!", "error"); return; }

  const cropTop    = parseInt(document.getElementById("crop-top")?.value   ?? 0);
  const cropBottom = parseInt(document.getElementById("crop-bottom")?.value ?? 0);
  const cropLeft   = parseInt(document.getElementById("crop-left")?.value  ?? 0);
  const cropRight  = parseInt(document.getElementById("crop-right")?.value ?? 0);
  const upscaleRes = document.getElementById("upscale-res")?.value ?? "";
  const loopDur    = parseInt(document.getElementById("video-loop-dur")?.value ?? 0);

  const payload = {
    input:       inputPath,
    output:      outputPath,
    crop_top:    cropTop,
    crop_bottom: cropBottom,
    crop_left:   cropLeft,
    crop_right:  cropRight,
    upscale:     upscaleRes || null,
    duration:    loopDur || null,
    video_duration: state.video.info?.duration ?? 8,
  };

  setPanelProcessing(P);
  clearLog(P);
  setProgress(P, 0);
  let totalSteps = 3;

  await processVideo(payload, (ev) => {
    if (ev.type === "pipeline_start") {
      totalSteps = ev.total_steps ?? 3;
    } else if (ev.type === "step_start") {
      setProgress(P, Math.round(((ev.step - 1) / totalSteps) * 100));
      log(P, `[${ev.step}/${totalSteps}] ${ev.label}`);
    } else if (ev.type === "step_done") {
      setProgress(P, Math.round((ev.step / totalSteps) * 100));
      log(P, `✅ ${ev.label} — ${ev.elapsed ?? ""} ${ev.output_size ?? ""}`, "done");
    } else if (ev.log) {
      log(P, ev.log);
    } else if (ev.status === "all_done" || ev.status === "done") {
      state.video.outputPath = ev.output ?? outputPath;
      state.video.ready = true;
      setProgress(P, 100);
      setPanelReady(P, (ev.output ?? outputPath).split(/[\\/]/).pop());
      toast("Video selesai!", "success");
      emit("video:ready", { path: ev.output ?? outputPath });
    } else if (ev.status === "error") {
      setPanelIdle(P);
      log(P, `❌ ${ev.message ?? "Error"}`, "error");
      toast("Proses video gagal.", "error");
    }
  });
}
