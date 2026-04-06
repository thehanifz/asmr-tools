/**
 * Panel Merge — handles merge + thumbnail + final export.
 * Activates automatically when both video:ready and audio:ready events fire.
 */
import { state } from "./state.js";
import { mergeFiles, makeThumbnail, openFolder, browseFolder } from "./api.js";
import { toast, log, clearLog, setStatus, setProgress, show, hide } from "./ui.js";

export function initMergePanel() {
  // Listen for panel-ready events
  document.addEventListener("video:ready", updateMergeReadiness);
  document.addEventListener("audio:ready", updateMergeReadiness);

  // Output folder browse
  document.getElementById("btn-browse-folder")?.addEventListener("click", async () => {
    const res = await browseFolder();
    if (res.path) {
      state.output.folder = res.path;
      document.getElementById("output-folder").value = res.path;
    }
  });

  // Duration presets
  document.querySelectorAll("[data-duration]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const val = parseInt(btn.dataset.duration);
      state.output.targetDuration = val;
      const input = document.getElementById("target-duration");
      if (input) input.value = val;
    });
  });

  // Merge button
  document.getElementById("btn-merge")?.addEventListener("click", runMerge);

  // Open folder button
  document.getElementById("btn-open-folder")?.addEventListener("click", () => {
    openFolder(state.output.folder);
  });
}

function updateMergeReadiness() {
  const btn = document.getElementById("btn-merge");
  if (!btn) return;
  const videoReady = state.video.ready;
  const audioReady = state.audio.ready;

  // Update source display in merge panel
  const videoLabel = document.getElementById("merge-video-label");
  const audioLabel = document.getElementById("merge-audio-label");
  if (videoLabel) videoLabel.textContent = videoReady
    ? `✅ ${state.video.outputPath?.split(/[\\/]/).pop()}`
    : "⏳ Belum diproses";
  if (audioLabel) audioLabel.textContent = audioReady
    ? `✅ ${state.audio.outputPath?.split(/[\\/]/).pop()}`
    : "⏳ Belum diproses";

  btn.disabled = !(videoReady && audioReady);
  btn.classList.toggle("btn-ready", videoReady && audioReady);
}

async function runMerge() {
  const { video, audio, output } = state;
  if (!video.outputPath || !audio.outputPath) {
    toast("Video dan Audio harus diproses dulu!", "error");
    return;
  }

  const folder = output.folder || document.getElementById("output-folder")?.value.trim();
  const thumbText1 = document.getElementById("thumb-text1")?.value.trim() ?? "";
  const thumbText2 = document.getElementById("thumb-text2")?.value.trim() ?? "";

  // Build output filename from video base
  const base = video.outputPath.split(/[\\/]/).pop().replace(/_video_looped\.mp4$/, "");
  const finalOutput = `${folder}\\${base}_final.mp4`;
  const thumbOutput = `${folder}\\${base}_thumbnail.jpg`;

  clearLog();
  setProgress(0);
  setStatus("Merging video + audio...");
  hide("btn-open-folder");

  // Step 1: Merge
  await mergeFiles(
    { video: video.outputPath, audio: audio.outputPath, output: finalOutput },
    (event) => {
      if (event.log) log(event.log);
      else if (event.type === "done") {
        setProgress(50);
        log(`✅ Merge selesai — ${event.size} (${event.elapsed})`, "success");
        setStatus("Generating thumbnail...");
      } else if (event.status === "error") {
        toast("Merge gagal.", "error");
        setStatus("❌ Merge error");
      }
    }
  );

  // Step 2: Thumbnail (from original video input)
  if (video.inputPath) {
    await makeThumbnail(
      {
        input: video.inputPath,
        output: thumbOutput,
        text1: thumbText1,
        text2: thumbText2,
      },
      (event) => {
        if (event.log) log(event.log);
        else if (event.status === "done") {
          setProgress(100);
          log(`🖼️ Thumbnail saved: ${thumbOutput}`, "success");
          setStatus("✅ Semua selesai!");
          toast("🎉 Export selesai!", "success");
          show("btn-open-folder");
        }
      }
    );
  } else {
    setProgress(100);
    setStatus("✅ Merge selesai!");
    show("btn-open-folder");
  }
}
