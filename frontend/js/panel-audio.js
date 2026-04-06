/**
 * Panel Audio — wired to HTML ids from index.html v2
 */
import { state, emit } from "./state.js";
import { probeFile, browseAudio, processAudio } from "./api.js";
import { toast, log, clearLog, setProgress,
         setPanelReady, setPanelProcessing, setPanelIdle, showProbe } from "./ui.js";

const P = "audio";

export function initAudioPanel() {
  document.getElementById("audio-browse")?.addEventListener("click", async () => {
    const res = await browseAudio();
    if (res?.path) await loadAudio(res.path);
  });

  document.getElementById("audio-run")?.addEventListener("click", runAudioProcess);

  document.getElementById("audio-path")?.addEventListener("change", (e) => {
    if (e.target.value) loadAudio(e.target.value);
  });
}

async function loadAudio(path) {
  state.audio.inputPath = path;
  const el = document.getElementById("audio-path");
  if (el) el.value = path;

  setPanelProcessing(P);
  const info = await probeFile(path);
  if (info.error) { toast(info.error, "error"); setPanelIdle(P); return; }

  state.audio.info = info;
  renderAudioProbe(info);
  showProbe(P);

  // Auto-suggest output
  const dir  = path.replace(/[\\/][^\\/]+$/, "");
  const base = path.split(/[\\/]/).pop().replace(/\.[^.]+$/, "");
  const outEl = document.getElementById("audio-output");
  if (outEl && !outEl.value) outEl.value = `${dir}\\${base}_looped.flac`;

  setPanelIdle(P);
}

function renderAudioProbe(info) {
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val ?? "—"; };
  set("a-dur",     info.duration_str);
  set("a-codec",   info.audio_codec);
  set("a-sr",      info.sample_rate ? `${info.sample_rate} Hz` : "—");
  set("a-ch",      info.channels);
  set("a-bitrate", info.bitrate_str);
  set("a-size",    info.size_str);
}

async function runAudioProcess() {
  const inputPath = state.audio.inputPath || document.getElementById("audio-path")?.value.trim();
  if (!inputPath) { toast("Pilih file audio dulu!", "error"); return; }

  const outputPath = document.getElementById("audio-output")?.value.trim();
  if (!outputPath) { toast("Isi path output audio!", "error"); return; }

  const loopDur = parseInt(document.getElementById("audio-loop-dur")?.value ?? 3600);
  const lufs    = parseFloat(document.getElementById("audio-lufs")?.value ?? "") || null;
  const fadeIn  = parseFloat(document.getElementById("audio-fade-in")?.value ?? 3);
  const fadeOut = parseFloat(document.getElementById("audio-fade-out")?.value ?? 5);

  const payload = {
    input:    inputPath,
    output:   outputPath,
    duration: loopDur,
    lufs:     lufs,
    fade_in:  fadeIn,
    fade_out: fadeOut,
  };

  setPanelProcessing(P);
  clearLog(P);
  setProgress(P, 0);

  await processAudio(payload, (ev) => {
    if (ev.log) {
      log(P, ev.log);
    } else if (ev.status === "done") {
      state.audio.outputPath = outputPath;
      state.audio.ready = true;
      setProgress(P, 100);
      setPanelReady(P, outputPath.split(/[\\/]/).pop());
      toast("Audio selesai!", "success");
      emit("audio:ready", { path: outputPath });
    } else if (ev.status === "error") {
      setPanelIdle(P);
      log(P, `❌ ${ev.message ?? "Error"}`, "error");
      toast("Proses audio gagal.", "error");
    }
  });
}
