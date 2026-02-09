/**
 * Suppress i18next's promotional "locize" console.log.
 *
 * This module MUST be imported in main.tsx BEFORE ./lib/i18n so that
 * the patched console.log is in place when i18next captures it at
 * module-init time (Vite code-splits i18next into a separate chunk).
 */
const _origLog = console.log;
console.log = (...args: unknown[]) => {
  if (typeof args[0] === "string" && args[0].includes("locize")) return;
  _origLog.apply(console, args);
};
