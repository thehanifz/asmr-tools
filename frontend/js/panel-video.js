// ═══════════════════════════════════════════════
//  Panel: Video Pipeline
//  v2.2.0 — xfade seamless loop + image duration toggle
// ═══════════════════════════════════════════════
import { AppState, setWorkspace, buildOutputPath } from './state.js';
import { browseVideo, probeFile }                  from './api.js';
import { toast, showFileInfo, consumeSSE }         from './ui.js';

export function initVideo() {
  const $ = id => document.getElementById(id);

  // ── Toggle .xfade-off class — tidak pakai .disabled, hanya CSS class ──
  function syncXfadeControls(enabled) {
    const wrap = $("xfadeControls");
    if (!wrap) return;
    wrap.classList.toggle("xfade-off", !enabled);
  }

  function syncImageDurationControls(enabled) {
    const wrap = $("imageDurationControls");
    if (!wrap) return;
    wrap.classList.toggle("xfade-off", !enabled);
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

  // ── Keep audio ────────────────────────────
  $("videoKeepAudio").addEventListener("change", e => {
    AppState.videoKeepAudio = e.target.checked;
  });

  // ── Image Duration toggle ───────────────────
  $("videoImageDurationEnabled").addEventListener("change", e => {
    syncImageDurationControls(e.target.checked);
  });
  syncImageDurationControls(false);

  // ── XFade toggle ───────────────────────────
  $("videoXfadeEnabled").addEventListener("change", e => {
    syncXfadeControls(e.target.checked);
  });
  syncXfadeControls(false);

  // ── Process ─────────────────────────────────
  $("videoProcess").addEventListener("click", async () => {
    const input = $("videoInput").value;
    if (!input) { toast("Pilih file video dulu", "error"); return; }

    const output        = $("videoOutput").value || buildOutputPath(input, "._processed", ".mp4");
    const xfadeEnabled  = $("videoXfadeEnabled").checked;
    const xfadeDuration = parseFloat($("videoXfadeDuration").value) || 1.0;
    const imageDurationEnabled = $("videoImageDurationEnabled").checked;
    const imageDuration = parseFloat($("videoImageDuration").value) || 5;

    const payload = {
      input,
      output,
      crop_top:       parseInt($("cropTop").value)      || 0,
      crop_bottom:    parseInt($("cropBottom").value)    || 0,
      crop_left:      parseInt($("cropLeft").value)      || 0,
      crop_right:     parseInt($("cropRight").value)     || 0,
      upscale:        $("upscaleRes").value,
      duration:       parseInt($("videoDuration").value) || 3600,
      video_duration: AppState.videoDuration,
      keep_audio:     AppState.videoKeepAudio,
      xfade_enabled:  xfadeEnabled,
      xfade_duration: xfadeDuration,
      image_duration_enabled: imageDurationEnabled,
      image_duration: imageDuration,
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
