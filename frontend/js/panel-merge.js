// ═══════════════════════════════════════════════
//  Panel: Merge — Video + Multi Audio
// ═══════════════════════════════════════════════
import { AppState, setWorkspace, buildOutputPath } from './state.js';
import { browseVideo, browseAudio }               from './api.js';
import { toast, consumeSSE }                      from './ui.js';

let audioLayerCount = 0;

function createAudioLayer(path = "", volume = 100, pan = "center") {
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
    <select class="layer-pan" title="Posisi stereo (pan ala qipadd)">
      <option value="left" ${pan === "left" ? "selected" : ""}>Kiri</option>
      <option value="center" ${pan === "center" ? "selected" : ""}>Tengah</option>
      <option value="right" ${pan === "right" ? "selected" : ""}>Kanan</option>
    </select>
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

/** Convert an absolute server path under media/ to its stream URL. */
export function mediaUrl(path) {
  const norm = (path || "").replace(/\\/g, "/");
  if (!norm.includes("/media/")) return "";
  return `/api/library/stream?path=${encodeURIComponent(path)}`;
}

/** Show the finished merge in the result player + download button. */
export function showMergeResult(path) {
  const url = mediaUrl(path);
  const wrap = document.getElementById("mergeResult");
  if (!url || !wrap) return;
  const player = document.getElementById("mergePlayer");
  const dl = document.getElementById("mergeDownload");
  const name = document.getElementById("mergeResultName");
  if (player) player.src = url;
  if (dl) {
    dl.href = url + "&dl=1";
    dl.setAttribute("download", path.split(/[\\/]/).pop() || "merge.mp4");
  }
  if (name) name.textContent = path.split(/[\\/]/).pop() || "";
  wrap.style.display = "block";
}

function updateMergeOutput() {
  const videoPath = document.getElementById("mergeVideo").value;
  if (videoPath) {
    document.getElementById("mergeOutput").value = buildOutputPath(videoPath, "._final", ".mp4");
  }
}

export function initMerge() {
  const $ = id => document.getElementById(id);

  const syncMergeAudioSource = () => {
    const isLayer = $("mergeAudioSourceLayer").checked;
    const btnAdd = $("addAudioLayer");
    const layersDiv = $("audioLayers");

    if (isLayer) {
      btnAdd.style.display = "none";
      layersDiv.innerHTML = "";
      const path = AppState.soundLayerOutputPath || "";
      const div = document.createElement("div");
      div.className = "audio-layer read-only-layer";
      div.innerHTML = `
        <input type="text" class="file-input layer-path" placeholder="Hasil Render Sound Layering (menunggu render...)" readonly value="${path}">
        <div class="audio-layer-vol">
          <input type="number" class="layer-vol" value="100" min="0" max="200" step="5" readonly>
          <span>%</span>
        </div>
        <select class="layer-pan" disabled title="Posisi stereo">
          <option value="center" selected>Tengah</option>
        </select>
      `;
      layersDiv.appendChild(div);
    } else {
      btnAdd.style.display = "";
      layersDiv.innerHTML = "";
      if (AppState.audioLoopedPath) {
        layersDiv.appendChild(createAudioLayer(AppState.audioLoopedPath, 100));
      } else {
        layersDiv.appendChild(createAudioLayer());
      }
    }
  };

  $("mergeAudioSourceManual").addEventListener("change", syncMergeAudioSource);
  $("mergeAudioSourceLayer").addEventListener("change", syncMergeAudioSource);

  $("mergeVideo").addEventListener("input", updateMergeOutput);
  $("mergeVideo").addEventListener("change", updateMergeOutput);

  // Ubah default: Sound Layer Output menjadi pilihan awal
  const radioLayer = document.getElementById("mergeAudioSourceLayer");
  if (radioLayer) radioLayer.checked = true;
  syncMergeAudioSource(); // trigger UI sesuai default baru

  // Auto-fill when navigating to merge
  document.querySelector('.nav-item[data-tool="merge"]')?.addEventListener("click", () => {
    if (AppState.mergeFinalPath) showMergeResult(AppState.mergeFinalPath);
    if (AppState.videoProcessedPath) {
      $("mergeVideo").value = AppState.videoProcessedPath;
      updateMergeOutput();
    }
    
    const isLayer = $("mergeAudioSourceLayer").checked;
    if (isLayer) {
      syncMergeAudioSource();
    } else {
      const layers = document.getElementById("audioLayers");
      if (layers.children.length === 0) {
        if (AppState.audioLoopedPath) {
          layers.appendChild(createAudioLayer(AppState.audioLoopedPath, 100));
        } else {
          layers.appendChild(createAudioLayer());
        }
        updateMergeOutput();
      }
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
      pan:    div.querySelector(".layer-pan")?.value || "center",
    })).filter(l => l.path);

    if (layers.length === 0) { toast("Tambahkan minimal 1 audio", "error"); return; }

    const output = $("mergeOutput").value || buildOutputPath(videoPath, "._final", ".mp4");

    const payload = { video: videoPath, audio_layers: layers, output };

    $("mergeProcess").disabled = true;
    const { ok, finalData } = await consumeSSE(
      "/api/merge", payload,
      "mergeLog", "mergeProgressWrap", "mergeProgressFill", "mergeProgressLabel"
    );

    if (!ok) {
      $("mergeProcess").disabled = false;
      toast("Merge gagal", "error");
      return;
    }

    AppState.mergeFinalPath = output;
    toast(`Merge selesai · ${finalData?.size || ""}`, "success");
    document.querySelector('.nav-item[data-tool="merge"]')?.classList.add("done");
    showMergeResult(output);

    // Finishing opsional: intro card + fade + thumbnail, jalan otomatis
    // setelah merge bila dicentang (standar channel Extra Dimension).
    if ($("finEnable")?.checked) {
      const finPayload = {
        input: output,
        audio_path: layers[0]?.path || "",
        scene_title: $("finSceneTitle").value.trim(),
        sound_line: $("finSoundLine").value.trim(),
        thumb_title: $("finThumbTitle").value.trim(),
        make_thumbnail: true,
      };
      const fin = await consumeSSE(
        "/api/finishing", finPayload,
        "mergeLog", "mergeProgressWrap", "mergeProgressFill", "mergeProgressLabel"
      );
      if (fin.ok && fin.finalData?.output) {
        AppState.mergeFinalPath = fin.finalData.output;
        toast(`Finishing selesai · ${fin.finalData.size || ""}`, "success");
        showMergeResult(fin.finalData.output);
        const thumb = fin.finalData.thumbnail;
        if (thumb) {
          const url = mediaUrl(thumb);
          if (url) {
            $("finThumbPreview").src = url;
            const dl = $("finThumbDownload");
            dl.href = url + "&dl=1";
            dl.setAttribute("download", thumb.split(/[\\/]/).pop() || "thumbnail.jpg");
            $("finThumbName").textContent = thumb.split(/[\\/]/).pop() || "";
            $("finResult").style.display = "block";
          }
        }
      } else {
        toast("Finishing gagal — hasil merge tetap tersimpan", "error");
      }
    }
    $("mergeProcess").disabled = false;
  });

  // Tampilkan/sembunyikan kolom finishing
  $("finEnable")?.addEventListener("change", () => {
    $("finFields").style.display = $("finEnable").checked ? "block" : "none";
  });
}
