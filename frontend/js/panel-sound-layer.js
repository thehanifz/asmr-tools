// ═══════════════════════════════════════════════
//  Panel: Sound Layer (Smart Mix & Random Place)
// ═══════════════════════════════════════════════
import { AppState, setWorkspace } from './state.js';
import { browseAudio, probeFile, browseFolderAudio, previewSoundLayer } from './api.js';
import { toast, showFileInfo, logClear, logAppend, consumeSSE } from './ui.js';

function $(id) { return document.getElementById(id); }

function renderPoolList() {
  const container = $("soundLayerPoolContainer");
  const list = $("soundLayerPoolList");
  if (!list) return;

  list.innerHTML = "";
  if (!AppState.soundLayerFiles || AppState.soundLayerFiles.length === 0) {
    container.classList.add("hidden");
    return;
  }

  container.classList.remove("hidden");

  AppState.soundLayerFiles.forEach(f => {
    const div = document.createElement("div");
    div.className = "pool-item";
    div.innerHTML = `
      <label class="checkbox-label" style="margin-bottom: 0;">
        <input type="checkbox" class="pool-checkbox" data-path="${f.path}" checked>
        <span class="checkmark"></span>
      </label>
      <span class="pool-item-name" title="${f.name}">${f.name}</span>
      <span class="pool-item-dur">${f.duration.toFixed(1)}s</span>
    `;
    list.appendChild(div);
  });
}

export function initSoundLayer() {
  // ── Silence slider label ─────────────────────
  const slider = $("soundLayerSilenceThreshold");
  const sliderVal = $("soundLayerSilenceThresholdVal");
  if (slider && sliderVal) {
    slider.addEventListener("input", e => {
      sliderVal.textContent = e.target.value + " dB";
    });
  }

  // ── Browse Main Sound ─────────────────────────
  $("soundLayerMainBrowse").addEventListener("click", async () => {
    try {
      const path = await browseAudio();
      if (!path) return;
      $("soundLayerMain").value = path;
      setWorkspace(path);
      AppState.soundLayerMainPath = path;

      const info = await probeFile(path);
      if (info && !info.error) {
        showFileInfo("soundLayerMainInfo", info);
        AppState.soundLayerMainDuration = info.duration;
      }
    } catch (e) {
      console.error("[soundLayerMainBrowse]", e);
      toast("Gagal membuka file browser", "error");
    }
  });

  // ── Browse Optional Sound Pool Folder ────────
  $("soundLayerFolderBrowse").addEventListener("click", async () => {
    try {
      const data = await browseFolderAudio();
      if (!data || !data.path) return;
      $("soundLayerFolder").value = data.path;
      AppState.soundLayerFolderPath = data.path;
      AppState.soundLayerFiles = data.files || [];
      renderPoolList();
    } catch (e) {
      console.error("[soundLayerFolderBrowse]", e);
      toast("Gagal membuka folder browser", "error");
    }
  });

  // ── All / None Buttons ──────────────────────
  $("soundLayerPoolAll").addEventListener("click", () => {
    document.querySelectorAll("#soundLayerPoolList .pool-checkbox").forEach(cb => cb.checked = true);
  });

  $("soundLayerPoolNone").addEventListener("click", () => {
    document.querySelectorAll("#soundLayerPoolList .pool-checkbox").forEach(cb => cb.checked = false);
  });

  // ── Preview Placement ────────────────────────
  $("soundLayerPreviewBtn").addEventListener("click", async () => {
    const mainSound = $("soundLayerMain").value.trim();
    const folder = $("soundLayerFolder").value.trim();
    if (!mainSound) { toast("Pilih main sound dulu", "error"); return; }
    if (!folder) { toast("Pilih folder optional sound dulu", "error"); return; }

    const checkboxes = document.querySelectorAll("#soundLayerPoolList .pool-checkbox:checked");
    const includedFiles = Array.from(checkboxes).map(cb => cb.dataset.path);

    if (includedFiles.length === 0) {
      toast("Pilih minimal satu file opsional dari pool", "error");
      return;
    }

    logClear("soundLayerLog");
    logAppend("soundLayerLog", "Membuat rencana penempatan...");

    const occurrences = parseInt($("soundLayerOccurrences").value) || 10;
    const minGap = parseFloat($("soundLayerMinGap").value) || 5;
    const allowOverlap = $("soundLayerAllowOverlap").checked;
    
    // Window percent to seconds
    const mainDuration = AppState.soundLayerMainDuration || 0;
    if (!mainDuration) {
      toast("Gagal mendapatkan durasi file utama. Coba pilih ulang file utama.", "error");
      return;
    }
    const winStartPct = parseFloat($("soundLayerWindowStart").value) || 0;
    const winEndPct = parseFloat($("soundLayerWindowEnd").value) || 100;
    const timeWindowStart = (winStartPct / 100) * mainDuration;
    const timeWindowEnd = (winEndPct / 100) * mainDuration;

    const minDur = parseFloat($("soundLayerMinDur").value) || 3;
    const maxDur = parseFloat($("soundLayerMaxDur").value) || 15;
    const fadeIn = parseFloat($("soundLayerFadeIn").value) || 1.5;
    const fadeOut = parseFloat($("soundLayerFadeOut").value) || 1.5;
    const silenceThresh = parseFloat($("soundLayerSilenceThreshold").value) || -40;

    const payload = {
      main_sound: mainSound,
      optional_sounds_folder: folder,
      included_files: includedFiles,
      occurrence_count: occurrences,
      time_window_start: timeWindowStart,
      time_window_end: timeWindowEnd,
      min_duration: minDur,
      max_duration: maxDur,
      min_gap: minGap,
      overlap_mode: allowOverlap ? "full" : "none",
      fade_duration: Math.max(fadeIn, fadeOut),
      silence_threshold: silenceThresh
    };

    try {
      $("soundLayerPreviewBtn").disabled = true;
      const res = await previewSoundLayer(payload);
      $("soundLayerPreviewBtn").disabled = false;

      if (res.error) {
        toast("Gagal mempratinjau penempatan: " + res.error, "error");
        logAppend("soundLayerLog", `✗ Error: ${res.error}`, "error");
        return;
      }

      AppState.soundLayerPlan = res;
      
      logClear("soundLayerLog");
      logAppend("soundLayerLog", `✓ Rencana penempatan berhasil dibuat (Total: ${res.placements.length} penempatan)`, "done");
      res.placements.forEach((p, idx) => {
        const name = p.source_file.split(/[/\\]/).pop();
        logAppend("soundLayerLog", `[Placement ${idx + 1}] ${name}`);
        logAppend(
          "soundLayerLog",
          `  • Start: ${p.start_time.toFixed(2)}s | Durasi: ${p.duration.toFixed(2)}s (Fade In: ${p.fade_in}s, Out: ${p.fade_out}s)`
        );
        if (p.trimmed_start > 0 || p.trimmed_end > 0) {
          logAppend(
            "soundLayerLog",
            `  • Silence trimmed: start ${p.trimmed_start.toFixed(2)}s, end ${p.trimmed_end.toFixed(2)}s`
          );
        }
      });
      toast("Rencana penempatan berhasil dibuat. Siap untuk render!", "success");
    } catch (e) {
      $("soundLayerPreviewBtn").disabled = false;
      logAppend("soundLayerLog", `✗ Error: ${e.message}`, "error");
      toast("Preview error: " + e.message, "error");
    }
  });

  // ── Render Mix ──────────────────────────────
  $("soundLayerRenderBtn").addEventListener("click", async () => {
    if (!AppState.soundLayerPlan) {
      toast("Silakan buat rencana penempatan dengan klik Preview Placement dahulu", "warning");
      return;
    }

    const btn = $("soundLayerRenderBtn");
    btn.disabled = true;
    btn.textContent = "⏳ Rendering...";

    try {
      const silenceThresh = parseFloat($("soundLayerSilenceThreshold").value) || -40;
      const mainSound = AppState.soundLayerPlan.main_sound_path;
      const base = mainSound.substring(0, mainSound.lastIndexOf("."));
      const outputSuggested = base + "._layered.m4a";

      const payload = {
        plan: AppState.soundLayerPlan,
        output_path: outputSuggested,
        silence_threshold: silenceThresh
      };

      const { ok, finalData } = await consumeSSE(
        "/api/sound-layer/render",
        payload,
        "soundLayerLog",
        "soundLayerProgressWrap",
        "soundLayerProgressFill",
        "soundLayerProgressLabel"
      );

      btn.disabled = false;
      btn.textContent = "▶ Render Mix";

      if (ok && finalData) {
        AppState.soundLayerOutputPath = finalData.output || outputSuggested;
        toast(`✓ Render selesai · ${finalData.size || ""}`, "success");
        document.querySelector('.nav-item[data-tool="sound-layer"]')?.classList.add("done");

        // Set up the player
        const playerContainer = $("soundLayerPlayerContainer");
        const audioPlayer = $("soundLayerAudioPlayer");
        if (playerContainer && audioPlayer) {
          playerContainer.style.display = "flex";
          audioPlayer.src = `/api/sound-layer/play?path=${encodeURIComponent(AppState.soundLayerOutputPath)}`;
          audioPlayer.load();
        }
      } else {
        toast("Rendering gagal — cek log", "error");
      }
    } catch (e) {
      console.error("[soundLayerRenderBtn]", e);
      btn.disabled = false;
      btn.textContent = "▶ Render Mix";
      toast(`Error: ${e.message}`, "error");
    }
  });
}
