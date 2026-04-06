/**
 * Global state — single source of truth for the entire app.
 * Import this in any panel module; never duplicate state elsewhere.
 */
export const state = {
  video: {
    inputPath: null,
    info: null,          // from /api/probe
    outputPath: null,    // video_looped.mp4 after processing
    ready: false,
  },
  audio: {
    inputPath: null,
    info: null,
    outputPath: null,    // audio_looped.m4a after processing
    ready: false,
  },
  output: {
    folder: "",
    targetDuration: 3600,
    thumbText1: "",
    thumbText2: "",
  },
};

/** Emit a custom DOM event so panels can react to state changes. */
export function emit(eventName, detail = {}) {
  document.dispatchEvent(new CustomEvent(eventName, { detail }));
}
