//! Context categories use the engine's estimate, not lifetime token usage.
/** @typedef {{ key: string, bytes: number, tokens: number }} Section */
/** @typedef {{ model: string, sections: Section[], system: number, fixed: number, tools: number | null, valid: boolean, promptAvailable?: boolean, stale?: boolean, skillOverhead?: { bytes: number, tokens: number }, sources: { scope: string, path: string }[], skills: { name: string, scope: string, description: string, bytes?: number | null, tokens?: number | null }[] }} Snapshot */
/** @typedef {{ label: string, tokens: number, group: string, glyph: string }} Category */

/** Build a non-overlapping context breakdown. A null snapshot leaves usage unattributed. Category counts are estimates; cached input remains occupied context. */
/** @param {number} used @param {number} window @param {Snapshot | null} saved */
export function breakdown(used, window, saved) {
  const reserve = window > 0 ? Math.max(Math.floor(window / 10), Math.min(16384, Math.floor(window / 4))) : 0;
  const compactAt = Math.max(0, window - reserve);
  /** @type {Category[]} */
  const categories = [];
  const attributed = !!saved?.valid && saved.fixed <= used;
  const promptAttributed = !!(saved?.promptAvailable || saved?.valid) && !!saved && saved.system <= used;
  if (promptAttributed && saved) {
    let system = 0;
    let instructions = 0;
    let skills = 0;
    for (let i = 0; i < saved.sections.length; i++) {
      const section = saved.sections[i];
      if (section.key === "instructions") instructions += section.tokens;
      else if (section.key === "skills") skills += section.tokens;
      else system += section.tokens;
    }
    categories.push(
      { label: "System + plugin instructions", tokens: system, group: "ContextSystem", glyph: "■" },
      { label: "AGENTS.md instructions", tokens: instructions, group: "ContextInstructions", glyph: "■" },
      { label: "Skill catalog", tokens: skills, group: "ContextSkills", glyph: "■" },
      { label: "Tools / request overhead", tokens: attributed ? saved.tools ?? 0 : 0, group: "ContextTools", glyph: "■" },
      { label: attributed ? "Chat + tool results + reasoning" : "Chat + tools (unattributed)", tokens: used - (attributed ? saved.fixed : saved.system), group: "ContextChat", glyph: "■" },
    );
  } else categories.push({ label: "Context (split unavailable)", tokens: used, group: "ContextChat", glyph: "■" });
  if (window > 0) categories.push(
    { label: "Free until auto-compaction", tokens: Math.max(0, compactAt - used), group: "ContextFree", glyph: "□" },
    { label: "Remaining safety reserve", tokens: Math.max(0, window - Math.max(compactAt, used)), group: "ContextReserve", glyph: "▧" },
  );
  return { categories, attributed, promptAttributed, reserve, compactAt };
}

/** Allocate a fixed square grid by largest remainder. The grid uses the whole window; an overflow fills it and the UI reports the excess. No minimum square inflates a small category. */
/** @param {Category[]} categories @param {number} cells @returns {{ glyph: string, group: string }[]} */
export function squares(categories, cells) {
  const total = categories.reduce((sum, category) => sum + category.tokens, 0);
  if (total <= 0) return [];
  const shares = categories.map((category, index) => {
    const raw = category.tokens / total * cells;
    return { index, count: Math.floor(raw), remainder: raw - Math.floor(raw) };
  });
  let remaining = cells - shares.reduce((sum, share) => sum + share.count, 0);
  const ranked = shares.slice().sort((a, b) => b.remainder - a.remainder || a.index - b.index);
  for (let i = 0; i < ranked.length && remaining > 0; i++, remaining--) ranked[i].count++;
  const result = [];
  for (let i = 0; i < shares.length; i++) {
    const category = categories[i];
    for (let n = 0; n < shares[i].count; n++) result.push({ glyph: category.glyph, group: category.group });
  }
  return result;
}
