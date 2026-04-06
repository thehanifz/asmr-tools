/**
 * main.js — App entry point.
 * Imports and initialises all panels.
 */
import { initVideoPanel } from "./panel-video.js";
import { initAudioPanel } from "./panel-audio.js";
import { initMergePanel } from "./panel-merge.js";

document.addEventListener("DOMContentLoaded", () => {
  initVideoPanel();
  initAudioPanel();
  initMergePanel();

  // Output folder input sync → state
  const folderInput = document.getElementById("output-folder");
  folderInput?.addEventListener("change", () => {
    const { state } = window._state ?? {}; // fallback if needed
  });

  // Target duration input sync
  const durationInput = document.getElementById("target-duration");
  durationInput?.addEventListener("input", () => {
    const secs = parseInt(durationInput.value);
    const label = document.getElementById("duration-label");
    if (label && secs) {
      const h = Math.floor(secs / 3600);
      const m = Math.floor((secs % 3600) / 60);
      label.textContent = h > 0 ? `= ${h} jam ${m} menit` : `= ${m} menit`;
    }
  });
});
