// ═══════════════════════════════════════════════
//  Panel: Thumbnail
// ═══════════════════════════════════════════════
import { AppState, setWorkspace, buildOutputPath } from './state.js';
import { browseVideo, probeFile, extractThumbnail, thumbnailPreviewUrl } from './api.js';
import { toast, showFileInfo, logAppend, logClear } from './ui.js';

export function initThumbnail() {
  const $ = id => document.getElementById(id);

  let videoDuration = 5.0;

  async function loadVideo(path) {
    $("thumbInput").value = path;
    setWorkspace(path);
    AppState.thumbnailSourcePath = path;
    $("thumbOutput").value = buildOutputPath(path, "_thumb", ".jpg");
    const info = await probeFile(path);
    if (!info.error) {
      showFileInfo("thumbInfo", info);
      videoDuration = info.duration || 5.0;
    }
  }

  // Auto-fill from Video Pipeline
  document.querySelector('.nav-item[data-tool="thumbnail"]')?.addEventListener("click", () => {
    if (AppState.videoProcessedPath && !$("thumbInput").value) {
      loadVideo(AppState.videoProcessedPath);
    }
  });

  $("thumbBrowse").addEventListener("click", async () => {
    const path = await browseVideo();
    if (!path) return;
    loadVideo(path);
  });

  // Start Frame capture (0s)
  $("thumbStartFrameBtn")?.addEventListener("click", async () => {
    const input = $("thumbInput").value;
    if (!input) { toast("Pilih file video dulu", "error"); return; }
    $("thumbTime").value = 0;
    $("thumbOutput").value = buildOutputPath(input, "_frame_awal", ".jpg");
    $("thumbProcess").click();
  });

  // End Frame capture (last second)
  $("thumbEndFrameBtn")?.addEventListener("click", async () => {
    const input = $("thumbInput").value;
    if (!input) { toast("Pilih file video dulu", "error"); return; }
    const endSec = Math.max(0, videoDuration - 0.1);
    $("thumbTime").value = endSec.toFixed(2);
    $("thumbOutput").value = buildOutputPath(input, "_frame_akhir", ".jpg");
    $("thumbProcess").click();
  });

  $("thumbProcess").addEventListener("click", async () => {
    const input = $("thumbInput").value;
    if (!input) { toast("Pilih file video dulu", "error"); return; }

    const timeSec = parseFloat($("thumbTime").value) || 0;
    const output  = $("thumbOutput").value || buildOutputPath(input, "_thumb", ".jpg");

    logClear("thumbLog");
    logAppend("thumbLog", "Extracting thumbnail...");
    $("thumbProcess").disabled = true;

    const result = await extractThumbnail({
      input,
      output,
      time_sec: timeSec,
      text1:  $("thumbText1").value,
      text2:  $("thumbText2").value,
      color:  $("thumbColor").value,
    });

    $("thumbProcess").disabled = false;

    if (result.error) {
      logAppend("thumbLog", `✗ ${result.error}`, "error");
      toast("Thumbnail gagal", "error");
      return;
    }

    logAppend("thumbLog", `✓ ${result.output}`, "done");
    AppState.thumbnailOutputPath = result.output;
    toast("Thumbnail berhasil", "success");

    // Preview
    const preview = $("thumbPreview");
    preview.innerHTML = `<img src="${thumbnailPreviewUrl(result.output)}?t=${Date.now()}" alt="Thumbnail preview">`;
    preview.classList.add("visible");
  });
}
