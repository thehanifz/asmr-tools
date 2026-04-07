// ═══════════════════════════════════════════════
//  Panel: Thumbnail
// ═══════════════════════════════════════════════
import { AppState, setWorkspace, buildOutputPath } from './state.js';
import { browseVideo, probeFile, extractThumbnail, thumbnailPreviewUrl } from './api.js';
import { toast, showFileInfo, logAppend, logClear } from './ui.js';

export function initThumbnail() {
  const $ = id => document.getElementById(id);

  // Auto-fill from Video Pipeline
  document.querySelector('.nav-item[data-tool="thumbnail"]')?.addEventListener("click", () => {
    if (AppState.videoProcessedPath && !$("thumbInput").value) {
      $("thumbInput").value = AppState.videoProcessedPath;
      $("thumbOutput").value = buildOutputPath(AppState.videoProcessedPath, "_thumb", ".jpg");
    }
  });

  $("thumbBrowse").addEventListener("click", async () => {
    const path = await browseVideo();
    if (!path) return;
    $("thumbInput").value = path;
    setWorkspace(path);
    AppState.thumbnailSourcePath = path;
    $("thumbOutput").value = buildOutputPath(path, "_thumb", ".jpg");
    const info = await probeFile(path);
    if (!info.error) showFileInfo("thumbInfo", info);
  });

  $("thumbProcess").addEventListener("click", async () => {
    const input = $("thumbInput").value;
    if (!input) { toast("Pilih file video dulu", "error"); return; }

    const timeSec = parseFloat($("thumbTime").value) || 5;
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
