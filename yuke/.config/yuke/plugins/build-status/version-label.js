/** Compact a UI build label without changing its package version or dirty marker. @param {string} version @returns {string} */
export function versionLabel(version) {
  return version.replace(/\.b\d{14}$/, "").replace(/\+([0-9a-f]{8})[0-9a-f]+(?=\.dirty$|$)/, "+$1");
}
