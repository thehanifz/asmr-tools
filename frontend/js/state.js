// ═══════════════════════════════════════════════
//  AppState — Global state, persists across tools
// ═══════════════════════════════════════════════

export const AppState = {
  // Workspace
  workspaceDir: "",

  // Video
  videoOriginalPath: "",
  videoProcessedPath: "",
  videoDuration: 8,          // source video duration in seconds
  videoKeepAudio: false,

  // Audio
  audioOriginalPath: "",
  audioDenoisedPath: "",
  audioLoopedPath: "",

  // Merge
  mergeAudioLayers: [],       // [{ path, volume }]
  mergeFinalPath: "",

  // Thumbnail
  thumbnailSourcePath: "",
  thumbnailOutputPath: "",

  // Sound Layer
  soundLayerMainPath: "",
  soundLayerFolderPath: "",
  soundLayerFiles: [],
  soundLayerPlan: null,
  soundLayerOutputPath: "",
};

// ── Path helpers ─────────────────────────────────

/**
 * Extract directory from a full file path.
 * Works for both "/" and "\\" separators.
 */
export function dirOf(filepath) {
  if (!filepath) return "";
  const norm = filepath.replace(/\\/g, "/");
  return norm.substring(0, norm.lastIndexOf("/") + 1);
}

/**
 * Build an output path in the same folder as inputPath.
 * Replaces extension and adds suffix.
 * e.g. buildOutputPath("C:/x/video.mp4", "_processed", ".mp4")
 *      → "C:/x/video._processed.mp4"
 */
export function buildOutputPath(inputPath, suffix, ext) {
  if (!inputPath) return "";
  const norm = inputPath.replace(/\\/g, "/");
  const lastSlash = norm.lastIndexOf("/");
  const dir = lastSlash !== -1 ? norm.substring(0, lastSlash + 1) : "";
  const filePart = lastSlash !== -1 ? norm.substring(lastSlash + 1) : norm;
  const lastDot = filePart.lastIndexOf(".");
  const filename = lastDot !== -1 ? filePart.substring(0, lastDot) : filePart;

  let prefix = suffix;
  if (prefix.startsWith("._")) prefix = prefix.substring(2);
  else if (prefix.startsWith("_")) prefix = prefix.substring(1);
  else if (prefix.startsWith(".")) prefix = prefix.substring(1);

  if (prefix === "cropped") prefix = "crop";
  else if (prefix === "looped") prefix = "loop";
  else if (prefix === "denoised") prefix = "denoise";
  else if (prefix === "audio") prefix = "extract";
  else if (prefix === "final") prefix = "merge";
  else if (prefix === "thumb") prefix = "thumb";

  return dir + prefix + "_" + filename + ext;
}

/**
 * Set workspace dir from any file path.
 * Only updates if the new dir is non-empty.
 */
export function setWorkspace(filepath) {
  const dir = dirOf(filepath);
  if (dir) {
    AppState.workspaceDir = dir;
    const el = document.getElementById("workspacePath");
    if (el) el.textContent = dir.replace(/\//g, "\\");
  }
}
