// ═══════════════════════════════════════════════
//  Panel: Merge — Video + Multi Audio
// ═══════════════════════════════════════════════
import { AppState, setWorkspace, buildOutputPath } from './state.js';
import { browseVideo, browseAudio }               from './api.js';
import { toast, consumeSSE }                      from './ui.js';

let audioLayerCount = 0;

function createAudioLayer(path = "", volume = 100) {
  const id = ++audioLayerCount;
  const div = document.createElement("div");
  div.className = "audio-layer";
  div.dataset.layerId = id;
  div.innerHTML = `
    <input type="text" class="file-input layer-path" placeholder="Pilih audio..." readonly value="${path}">
    <div class="audio-layer-vol">
      <input type="number" class="layer-vol" value="${volume}" min="0" max="200" step="5">
      <span>%</span>
    </div>
    <button class="btn-remove" data-id="${id}" title="Hapus layer">×</button>
  `;
  // Browse click on path input
  div.querySelector(".layer-path").addEventListener("click", async () => {
    const p = await browseAudio();
    if (p) {
      div.querySelector(".layer-path").value = p;
      setWorkspace(p);
    }
  });
  // Remove
  div.querySelector(".btn-remove").addEventListener("click", () => {
    div.remove();
    updateMergeOutput();
  });
  return div;
}

function updateMergeOutput() {
  const videoPath = document.getElementById("mergeVideo").value;
  if (videoPath) {
    document.getElementById("mergeOutput").value = buildOutputPath(videoPath, "._final", ".mp4");
  }
}

export function initMerge() {
  const $ = id => document.getElementById(id);

  // Auto-fill when navigating to merge
  document.querySelector('.nav-item[data-tool="merge"]')?.addEventListener("click", () => {
    if (AppState.videoProcessedPath && !$("mergeVideo").value) {
      $("mergeVideo").value = AppState.videoProcessedPath;
      updateMergeOutput();
    }
    // Add first audio layer from looped path if none exist
    const layers = document.getElementById("audioLayers");
    if (layers.children.length === 0 && AppState.audioLoopedPath) {
      layers.appendChild(createAudioLayer(AppState.audioLoopedPath, 100));
      updateMergeOutput();
    }
  });

  // Browse video
  $("mergeVideoBrowse").addEventListener("click", async () => {
    const p = await browseVideo();
    if (!p) return;
    $("mergeVideo").value = p;
    setWorkspace(p);
    updateMergeOutput();
  });

  // Add audio layer
  $("addAudioLayer").addEventListener("click", () => {
    const layers = $("audioLayers");
    if (layers.children.length >= 4) {
      toast("Maksimal 4 layer audio", "error");
      return;
    }
    layers.appendChild(createAudioLayer());
  });

  // Process merge
  $("mergeProcess").addEventListener("click", async () => {
    const videoPath = $("mergeVideo").value;
    if (!videoPath) { toast("Pilih file video dulu", "error"); return; }

    // Collect audio layers
    const layers = [...$("audioLayers").querySelectorAll(".audio-layer")].map(div => ({
      path:   div.querySelector(".layer-path").value,
      volume: parseInt(div.querySelector(".layer-vol").value) || 100,
    })).filter(l => l.path);

    if (layers.length === 0) { toast("Tambahkan minimal 1 audio", "error"); return; }

    const output = $("mergeOutput").value || buildOutputPath(videoPath, "._final", ".mp4");

    const payload = { video: videoPath, audio_layers: layers, output };

    $("mergeProcess").disabled = true;
    const { ok, finalData } = await consumeSSE(
      "/api/merge", payload,
      "mergeLog", "mergeProgressWrap", "mergeProgressFill", "mergeProgressLabel"
    );
    $("mergeProcess").disabled = false;

    if (ok) {
      AppState.mergeFinalPath = output;
      toast(`Merge selesai · ${finalData?.size || ""}`, "success");
      document.querySelector('.nav-item[data-tool="merge"]')?.classList.add("done");
    } else {
      toast("Merge gagal", "error");
    }
  });
}
