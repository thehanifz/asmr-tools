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
  AppState.mainSounds = []; // Array of {path, volume}

  function renderMainSoundsList() {
    const list = $("soundLayerMainList");
    if (!list) return;
    list.innerHTML = "";
    
    $("soundLayerAddMainBtn").disabled = AppState.mainSounds.length >= 3;

    AppState.mainSounds.forEach((snd, idx) => {
      const div = document.createElement("div");
      div.className = "file-row";
      div.style.flexDirection = "column";
      div.style.alignItems = "stretch";
      div.style.gap = "8px";
      div.style.padding = "10px";
      div.style.background = "var(--bg-hover)";
      div.style.borderRadius = "6px";
      
      div.innerHTML = `
        <div style="display:flex; gap:8px; align-items:center;">
          <input type="text" class="file-input" value="${snd.path}" readonly style="flex:1;">
          <button class="btn btn-ghost" style="color:var(--danger);" data-idx="${idx}">Hapus</button>
        </div>
        <div style="display:flex; gap:12px; align-items:center;">
          <label style="font-size:12px; min-width:50px;">Volume</label>
          <input type="range" class="slider vol-slider" data-idx="${idx}" min="0" max="100" value="${snd.volume}" style="flex:1;">
          <span style="font-family:var(--font-mono); font-size:12px; width:40px; text-align:right;">${snd.volume}%</span>
        </div>
      `;
      
      // Hapus event
      div.querySelector(".btn-ghost").addEventListener("click", (e) => {
        const i = parseInt(e.target.dataset.idx);
        AppState.mainSounds.splice(i, 1);
        renderMainSoundsList();
      });
      
      // Volume event
      const volSlider = div.querySelector(".vol-slider");
      const volText = div.querySelector("span");
      volSlider.addEventListener("input", (e) => {
        const v = parseInt(e.target.value);
        volText.textContent = v + "%";
        AppState.mainSounds[parseInt(e.target.dataset.idx)].volume = v;
      });

      list.appendChild(div);
    });
  }

  $("soundLayerAddMainBtn").addEventListener("click", async () => {
    if (AppState.mainSounds.length >= 3) return;
    try {
      const path = await browseAudio();
      if (!path) return;
      setWorkspace(path);
      
      AppState.mainSounds.push({ path: path, volume: 100 });
      renderMainSoundsList();
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

  // ── Preview Placement (Plan Layers) ────────────────────────
  $("soundLayerPreviewPlanBtn").addEventListener("click", async () => {
    const folder = $("soundLayerFolder").value.trim();
    if (AppState.mainSounds.length === 0) { toast("Pilih minimal 1 main sound", "error"); return; }

    const checkboxes = document.querySelectorAll("#soundLayerPoolList .pool-checkbox:checked");
    const includedFiles = Array.from(checkboxes).map(cb => cb.dataset.path);

    logClear("soundLayerLog");
    logAppend("soundLayerLog", "Membuat rencana penempatan...");

    const occurrences = parseInt($("soundLayerOccurrences").value) || 10;
    const minGap = parseFloat($("soundLayerMinGap").value) || 5;
    const allowOverlap = $("soundLayerAllowOverlap").checked;
    
    // Target duration instead of mainDuration
    const targetDuration = parseFloat($("soundLayerTargetDuration").value) || 3600;
    const loopXfade = parseFloat($("soundLayerLoopXfade").value) || 2.0;
    const outFormat = $("soundLayerOutputFormat").value || "aac";

    const winStartPct = parseFloat($("soundLayerWindowStart").value) || 0;
    const winEndPct = parseFloat($("soundLayerWindowEnd").value) || 100;
    const timeWindowStart = (winStartPct / 100) * targetDuration;
    const timeWindowEnd = (winEndPct / 100) * targetDuration;

    const minDur = parseFloat($("soundLayerMinDur").value) || 3;
    const maxDur = parseFloat($("soundLayerMaxDur").value) || 15;
    const fadeIn = parseFloat($("soundLayerFadeIn").value) || 1.5;
    const fadeOut = parseFloat($("soundLayerFadeOut").value) || 1.5;
    const silenceThresh = parseFloat($("soundLayerSilenceThreshold").value) || -40;

    const payload = {
      main_sounds: AppState.mainSounds,
      optional_sounds_folder: folder,
      included_files: includedFiles,
      target_duration: targetDuration,
      loop_xfade: loopXfade,
      output_format: outFormat,
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
      $("soundLayerPreviewPlanBtn").disabled = true;
      const res = await previewSoundLayer(payload);
      $("soundLayerPreviewPlanBtn").disabled = false;

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
      $("soundLayerPreviewPlanBtn").disabled = false;
      logAppend("soundLayerLog", `✗ Error: ${e.message}`, "error");
      toast("Preview error: " + e.message, "error");
    }
  });

  // ── Preview Mix (15s) ────────────────────────
  $("soundLayerPreviewMixBtn").addEventListener("click", async () => {
    doRender(true);
  });

  // ── Render Mix ──────────────────────────────
  $("soundLayerRenderBtn").addEventListener("click", async () => {
    doRender(false);
  });

  async function doRender(isPreviewMode) {
    if (!AppState.soundLayerPlan) {
      toast("Silakan buat rencana penempatan dengan klik 'Plan Layers' dahulu", "warning");
      return;
    }

    const btn = isPreviewMode ? $("soundLayerPreviewMixBtn") : $("soundLayerRenderBtn");
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = "⏳ Rendering...";

    try {
      const silenceThresh = parseFloat($("soundLayerSilenceThreshold").value) || -40;
      const outFormat = $("soundLayerOutputFormat").value || "aac";
      const loopXfade = parseFloat($("soundLayerLoopXfade").value) || 2.0;
      const targetDuration = parseFloat($("soundLayerTargetDuration").value) || 3600;
      
      const payload = {
        plan: AppState.soundLayerPlan,
        output_path: "", // Backend akan menentukan auto name
        silence_threshold: silenceThresh,
        preview_mode: isPreviewMode,
        output_format: outFormat,
        loop_xfade: loopXfade,
        target_duration: targetDuration
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
      btn.textContent = originalText;

      if (ok && finalData) {
        AppState.soundLayerOutputPath = finalData.output;
        toast(`✓ Render selesai · ${finalData.size || ""}`, "success");
        if (!isPreviewMode) {
          document.querySelector('.nav-item[data-tool="sound-layer"]')?.classList.add("done");
        }

        // Set up the player
        const playerContainer = $("soundLayerPlayerContainer");
        const audioPlayer = $("soundLayerAudioPlayer");
        if (playerContainer && audioPlayer) {
          playerContainer.style.display = "flex";
          // Append timestamp to bypass browser cache for preview mix re-renders
          audioPlayer.src = `/api/sound-layer/play?path=${encodeURIComponent(AppState.soundLayerOutputPath)}&t=${Date.now()}`;
          audioPlayer.load();
          if (isPreviewMode) {
            audioPlayer.play().catch(e => console.log("Auto-play blocked:", e));
          }
        }
      } else {
        toast("Rendering gagal — cek log", "error");
      }
    } catch (e) {
      console.error("[soundLayerRenderBtn]", e);
      btn.disabled = false;
      btn.textContent = originalText;
      toast(`Error: ${e.message}`, "error");
    }
  }
}
