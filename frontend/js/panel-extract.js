// ═══════════════════════════════════════════════
//  Panel: Extract Audio
// ═══════════════════════════════════════════════
import { AppState, setWorkspace, buildOutputPath } from './state.js';
import { browseVideo, probeFile }                  from './api.js';
import { toast, showFileInfo, consumeSSE }         from './ui.js';

export function initExtract() {
  const $ = id => document.getElementById(id);

  // ── Format change → update output extension ──
  $("extractFormat").addEventListener("change", () => {
    const input = $("extractInput").value;
    if (!input) return;
    const fmt = $("extractFormat").value;
    $("extractOutput").value = buildOutputPath(input, "_audio", "." + fmt);
  });

  // ── Browse ───────────────────────────────────
  $("extractBrowse").addEventListener("click", async () => {
    const path = await browseVideo();
    if (!path) return;
    $("extractInput").value = path;
    setWorkspace(path);
    const fmt = $("extractFormat").value || "mp3";
    $("extractOutput").value = buildOutputPath(path, "_audio", "." + fmt);
    const info = await probeFile(path);
    if (!info.error) showFileInfo("extractInfo", info);
  });

  // ── Browse Output ────────────────────────────
  $("extractOutputBrowse")?.addEventListener("click", async () => {
    const { browseFolder } = await import('./api.js');
    const folder = await browseFolder();
    if (!folder) return;
    const input = $("extractInput").value;
    const fmt   = $("extractFormat").value || "mp3";
    const base  = input ? input.replace(/\\/g, '/').split('/').pop().replace(/\.[^.]+$/, '') : 'audio';
    $("extractOutput").value = folder + '\\' + base + '_audio.' + fmt;
  });

  // ── Process ──────────────────────────────────
  $("extractProcess").addEventListener("click", async () => {
    const input = $("extractInput").value.trim();
    if (!input) { toast("Pilih file video dulu", "error"); return; }

    const fmt    = $("extractFormat").value || "mp3";
    const output = $("extractOutput").value.trim() || buildOutputPath(input, "_audio", "." + fmt);

    const payload = {
      input_path:  input,
      output_path: output,
      format:      fmt,
    };

    $("extractProcess").disabled = true;
    const { ok, finalData } = await consumeSSE(
      "/api/extract-audio", payload,
      "extractLog", "extractProgressWrap", "extractProgressFill", "extractProgressLabel"
    );
    $("extractProcess").disabled = false;

    if (ok) {
      AppState.extractedAudioPath = output;
      toast(`Extract selesai · ${fmt.toUpperCase()} · ${finalData?.size || ""}`, "success");
      document.querySelector('.nav-item[data-tool="extract"]')?.classList.add("done");

      // Auto-fill Denoise & Audio panel jika kosong
      const denoiseIn = document.getElementById("denoiseInput");
      if (denoiseIn && !denoiseIn.value) denoiseIn.value = output;
      const audioIn = document.getElementById("audioInput");
      if (audioIn && !audioIn.value) audioIn.value = output;
    } else {
      toast("Extract audio gagal", "error");
    }
  });
}
