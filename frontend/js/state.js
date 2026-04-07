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
  const lastDot = norm.lastIndexOf(".");
  const lastSlash = norm.lastIndexOf("/");
  const base = lastDot > lastSlash ? norm.substring(0, lastDot) : norm;
  return base + suffix + ext;
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
