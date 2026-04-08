// ═══════════════════════════════════════════════
//  Panel: Video Pipeline
// ═══════════════════════════════════════════════
import { AppState, setWorkspace, buildOutputPath } from './state.js';
import { browseVideo, probeFile }                  from './api.js';
import { toast, showFileInfo, consumeSSE }         from './ui.js';

export function initVideo() {
  const $ = id => document.getElementById(id);

  // ── Helper: sync state enable/disable input xfade ──
  function syncXfadeInputs(enabled) {
    const dur  = $("videoXfadeDuration");
    const type = $("videoXfadeType");
    if (!dur || !type) return;
    dur.disabled  = !enabled;
    type.disabled = !enabled;
    dur.style.opacity  = enabled ? "1" : "0.4";
    type.style.opacity = enabled ? "1" : "0.4";
  }

  // ── Browse ──────────────────────────────────
  $("videoBrowse").addEventListener("click", async () => {
    const path = await browseVideo();
    if (!path) return;
    $("videoInput").value = path;
    setWorkspace(path);
    AppState.videoOriginalPath = path;
    $("videoOutput").value = buildOutputPath(path, "._processed", ".mp4");
    const info = await probeFile(path);
    if (info.error) { toast(info.error, "error"); return; }
    showFileInfo("videoInfo", info);
    AppState.videoDuration = info.duration || 8;
  });

  // ── Keep audio checkbox ──────────────────────
  $("videoKeepAudio").addEventListener("change", e => {
    AppState.videoKeepAudio = e.target.checked;
  });

  // ── XFade toggle: enable/disable field input detik & tipe ──
  $("videoXfadeEnabled").addEventListener("change", e => {
    syncXfadeInputs(e.target.checked);
  });
  // Inisialisasi state awal (checkbox off → input disabled)
  syncXfadeInputs(false);

  // ── Process ─────────────────────────────────
  $("videoProcess").addEventListener("click", async () => {
    const input = $("videoInput").value;
    if (!input) { toast("Pilih file video dulu", "error"); return; }

    const output = $("videoOutput").value || buildOutputPath(input, "._processed", ".mp4");

    const xfadeEnabled  = $("videoXfadeEnabled").checked;
    const xfadeDuration = parseFloat($("videoXfadeDuration").value) || 1.0;

    const payload = {
      input,
      output,
      crop_top:       parseInt($("cropTop").value)    || 0,
      crop_bottom:    parseInt($("cropBottom").value)  || 0,
      crop_left:      parseInt($("cropLeft").value)    || 0,
      crop_right:     parseInt($("cropRight").value)   || 0,
      upscale:        $("upscaleRes").value,
      duration:       parseInt($("videoDuration").value) || 3600,
      video_duration: AppState.videoDuration,
      keep_audio:     AppState.videoKeepAudio,
      xfade_enabled:  xfadeEnabled,
      xfade_duration: xfadeDuration,
    };

    $("videoProcess").disabled = true;
    const { ok, finalData } = await consumeSSE(
      "/api/video/pipeline", payload,
      "videoLog", "videoProgressWrap", "videoProgressFill", "videoProgressLabel"
    );
    $("videoProcess").disabled = false;

    if (ok && finalData) {
      AppState.videoProcessedPath = finalData.output || output;
      toast(`Video selesai · ${finalData.final_size || ""}`, "success");
      document.querySelector('.nav-item[data-tool="video"]')?.classList.add("done");
    } else {
      toast("Video processing gagal", "error");
    }
  });
}
