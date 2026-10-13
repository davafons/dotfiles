//! Short elapsed labels for observed and estimated UI clocks.

/** Format elapsed milliseconds as an immutable h/m/s label. Spans below one second return "<1s"; negative spans clamp to zero. @param {number} ms @returns {string} */
export function elapsed(ms) {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  if (seconds === 0) return "<1s";
  if (seconds < 60) return seconds + "s";
  return longElapsed(seconds);
}

/** @param {number} seconds */
function longElapsed(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds / 60) % 60;
  const rest = seconds % 60;
  let text = hours ? hours + "h" : "";
  if (minutes) text += minutes + "m";
  if (rest) text += rest + "s";
  return text;
}
