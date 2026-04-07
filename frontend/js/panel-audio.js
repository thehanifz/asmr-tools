// ═══════════════════════════════════════════════
//  Panel: Audio Loop
// ═══════════════════════════════════════════════
import { AppState, setWorkspace, buildOutputPath } from './state.js';
import { browseAudio, probeFile }                  from './api.js';
import { toast, showFileInfo, consumeSSE }         from './ui.js';

export function initAudio() {
  const $ = id => document.getElementById(id);

  // ── Browse ──────────────────────────────────
  $("audioBrowse").addEventListener("click", async () => {
    // Prefer denoised file if available
    const path = await browseAudio();
    if (!path) return;
    $("audioInput").value = path;
    setWorkspace(path);
    AppState.audioOriginalPath = path;
    $("audioOutput").value = buildOutputPath(path, "._looped", ".m4a");
    const info = await probeFile(path);
    if (!info.error) showFileInfo("audioInfo", info);
  });

  // Auto-fill from denoise result when panel becomes active
  document.querySelector('.nav-item[data-tool="audio"]')?.addEventListener("click", () => {
    if (AppState.audioDenoisedPath && !$("audioInput").value) {
      $("audioInput").value = AppState.audioDenoisedPath;
      $("audioOutput").value = buildOutputPath(AppState.audioDenoisedPath, "._looped", ".m4a");
    }
  });

  // ── Process ─────────────────────────────────
  $("audioProcess").addEventListener("click", async () => {
    const input = $("audioInput").value;
    if (!input) { toast("Pilih file audio dulu", "error"); return; }

    const output = $("audioOutput").value || buildOutputPath(input, "._looped", ".m4a");
    const lufsRaw = $("audioLufs").value;

    const payload = {
      input,
      output,
      duration:  parseInt($("audioDuration").value) || 3600,
      lufs:      lufsRaw !== "" ? parseFloat(lufsRaw) : null,
      fade_in:   parseFloat($("audioFadeIn").value)  || 3,
      fade_out:  parseFloat($("audioFadeOut").value) || 5,
    };

    $("audioProcess").disabled = true;
    const { ok, finalData } = await consumeSSE(
      "/api/audio/loop", payload,
      "audioLog", "audioProgressWrap", "audioProgressFill", "audioProgressLabel"
    );
    $("audioProcess").disabled = false;

    if (ok) {
      AppState.audioLoopedPath = output;
      toast(`Audio selesai · ${finalData?.size || ""}`, "success");
      document.querySelector('.nav-item[data-tool="audio"]')?.classList.add("done");
    } else {
      toast("Audio processing gagal", "error");
    }
  });
}
