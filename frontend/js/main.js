/**
 * Entry point — initialise all panels.
 */
import { initVideoPanel } from "./panel-video.js";
import { initAudioPanel } from "./panel-audio.js";
import { initMergePanel } from "./panel-merge.js";

document.addEventListener("DOMContentLoaded", () => {
  initVideoPanel();
  initAudioPanel();
  initMergePanel();

  // FFmpeg badge check
  fetch("/api/probe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: "" }),
  })
    .then(() => {
      const badge = document.getElementById("ffmpeg-status");
      if (badge) { badge.textContent = "FFmpeg ✓"; badge.style.color = "var(--success)"; }
    })
    .catch(() => {
      const badge = document.getElementById("ffmpeg-status");
      if (badge) { badge.textContent = "FFmpeg ✗"; badge.style.color = "var(--error)";
                   badge.style.background = "var(--error-dim)"; }
    });
});
