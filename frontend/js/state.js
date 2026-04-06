/**
 * Global state — single source of truth.
 * Use emit() to dispatch custom DOM events.
 */
export const state = {
  video: { inputPath: "", info: null, outputPath: "", ready: false },
  audio: { inputPath: "", info: null, outputPath: "", ready: false },
};

export function emit(eventName, detail = {}) {
  document.dispatchEvent(new CustomEvent(eventName, { detail }));
}
