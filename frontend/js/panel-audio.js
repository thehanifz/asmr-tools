/**
 * Panel Audio — handles all logic for the Audio panel.
 * Responsibilities: file input, probe, loop/normalize/fade settings, process.
 */
import { state, emit } from "./state.js";
import { probeFile, browseAudio, processAudio } from "./api.js";
import { toast, log, clearLog, setStatus, setProgress, setPanelReady, setPanelProcessing, setPanelIdle } from "./ui.js";

const PANEL_ID = "panel-audio";

export function initAudioPanel() {
  document.getElementById("btn-browse-audio")?.addEventListener("click", async () => {
    const res = await browseAudio();
    if (res.path) loadAudioFile(res.path);
  });

  document.getElementById("btn-load-audio")?.addEventListener("click", () => {
    const path = document.getElementById("audio-path")?.value.trim();
    if (path) loadAudioFile(path);
  });

  const dropZone = document.getElementById("audio-drop-zone");
  dropZone?.addEventListener("dragover", (e) => e.preventDefault());
  dropZone?.addEventListener("drop", (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) loadAudioFile(file.path ?? file.name);
  });

  document.getElementById("btn-process-audio")?.addEventListener("click", runAudioProcess);
}

async function loadAudioFile(path) {
  state.audio.inputPath = path;
  document.getElementById("audio-path").value = path;
  setStatus("Probing audio...");
  const info = await probeFile(path);
  if (info.error) { toast(info.error, "error"); return; }
  state.audio.info = info;
  renderAudioInfo(info);
  setStatus("Audio loaded.");
}

function renderAudioInfo(info) {
  const box = document.getElementById("audio-info");
  if (!box) return;
  box.classList.remove("hidden");
  box.innerHTML = `
    <table>
      <tr><td>File</td><td>${info.filename}</td></tr>
      <tr><td>Durasi</td><td>${info.duration_str}</td></tr>
      <tr><td>Codec</td><td>${info.audio_codec ?? "-"}</td></tr>
      <tr><td>Channels</td><td>${info.channels ?? "-"}</td></tr>
      <tr><td>Sample Rate</td><td>${info.sample_rate ?? "-"} Hz</td></tr>
      <tr><td>Ukuran</td><td>${info.size_str}</td></tr>
    </table>
  `;
}

async function runAudioProcess() {
  const { inputPath } = state.audio;
  if (!inputPath) { toast("Pilih audio dulu!", "error"); return; }
  const outputDir = state.output.folder || document.getElementById("output-folder")?.value.trim();
  if (!outputDir) { toast("Set output folder dulu!", "error"); return; }

  const duration = parseInt(document.getElementById("target-duration")?.value ?? 3600);
  const volumeDb = parseFloat(document.getElementById("audio-volume")?.value ?? 0);
  const fadeIn = parseFloat(document.getElementById("audio-fade-in")?.value ?? 2);
  const fadeOut = parseFloat(document.getElementById("audio-fade-out")?.value ?? 3);
  const normalize = document.getElementById("audio-normalize")?.checked ?? true;

  const basename = inputPath.split(/[\\/]/).pop().replace(/\.[^.]+$/, "");
  const outputPath = `${outputDir}\\${basename}_audio_looped.m4a`;

  setPanelProcessing(PANEL_ID);
  clearLog();
  setProgress(0);
  setStatus("Processing audio...");

  await processAudio(
    { input: inputPath, output: outputPath, duration, volume_db: volumeDb, fade_in: fadeIn, fade_out: fadeOut, normalize },
    (event) => {
      if (event.log) {
        log(event.log);
      } else if (event.status === "done") {
        state.audio.outputPath = outputPath;
        state.audio.ready = true;
        setProgress(100);
        setStatus("✅ Audio selesai!");
        setPanelReady(PANEL_ID, outputPath.split(/[\\/]/).pop());
        toast("Audio selesai diproses!", "success");
        emit("audio:ready", { path: outputPath });
      } else if (event.status === "error") {
        setPanelIdle(PANEL_ID);
        setStatus("❌ Error saat proses audio");
        toast("Proses audio gagal.", "error");
      }
    }
  );
}
