// ═══════════════════════════════════════════════
//  Panel: Denoise Audio
// ═══════════════════════════════════════════════
import { AppState, setWorkspace, buildOutputPath } from './state.js';
import { browseAudio, probeFile }                  from './api.js';
import { toast, showFileInfo, logClear, logAppend, progressShow, progressDone } from './ui.js';

export function initDenoise() {
  const $ = id => document.getElementById(id);

  // ── Strength slider label ─────────────────────
  $("denoiseStrength").addEventListener("input", e => {
    $("denoiseStrengthVal").textContent = e.target.value + "%";
  });

  // ── Browse ──────────────────────────────────
  $("denoiseBrowse").addEventListener("click", async () => {
    const path = await browseAudio();
    if (!path) return;
    $("denoiseInput").value = path;
    setWorkspace(path);
    AppState.audioOriginalPath = path;
    $("denoiseOutput").value = buildOutputPath(path, "._denoised", ".wav");
    const info = await probeFile(path);
    if (!info.error) showFileInfo("denoiseInfo", info);
  });

  // ── Process ─────────────────────────────────
  $("denoiseProcess").addEventListener("click", async () => {
    const input = $("denoiseInput").value;
    if (!input) { toast("Pilih file audio dulu", "error"); return; }

    const output  = $("denoiseOutput").value || buildOutputPath(input, "._denoised", ".wav");
    const strength = parseInt($("denoiseStrength").value) / 100;
    const chunk    = parseInt($("denoiseChunk").value) || 30000;

    const payload = { input, output, strength, chunk };

    logClear("denoiseLog");
    progressShow("denoiseProgressWrap", "denoiseProgressFill", "denoiseProgressLabel", "Memproses denoise...");
    $("denoiseProcess").disabled = true;

    try {
      const res = await fetch("/api/denoise", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let ok = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop();
        for (const part of parts) {
          if (!part.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(part.slice(6));
            if (data.log)    logAppend("denoiseLog", data.log);
            if (data.status === "done") {
              ok = true;
              logAppend("denoiseLog", `✓ ${data.output}`, "done");
            }
            if (data.status === "error") {
              logAppend("denoiseLog", `✗ ${data.message || "Error"}`, "error");
            }
          } catch {}
        }
      }

      progressDone("denoiseProgressWrap", "denoiseProgressFill", "denoiseProgressLabel", ok ? "Selesai" : "Error");

      if (ok) {
        AppState.audioDenoisedPath = output;
        toast(`Denoise selesai → ${output.split(/[\/\\]/).pop()}`, "success");
        document.querySelector('.nav-item[data-tool="denoise"]')?.classList.add("done");
      } else {
        toast("Denoise gagal", "error");
      }
    } catch (err) {
      logAppend("denoiseLog", `✗ ${err.message}`, "error");
      toast("Denoise error: " + err.message, "error");
    } finally {
      $("denoiseProcess").disabled = false;
    }
  });
}
