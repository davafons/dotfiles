/** @param {unknown} actual @param {unknown} expected */
function equal(actual, expected) {
  if (actual !== expected) throw new Error("Expected " + expected + ", got " + actual);
}
import { breakdown, squares } from "../plugins/context-model.js";

const saved = { model: "test/model", system: 6000, sources: [], skills: [], valid: true, fixed: 8000, tools: 2000, sections: [
  { key: "base", tokens: 500, bytes: 2000 }, { key: "instructions", tokens: 2500, bytes: 10000 },
  { key: "skills", tokens: 2500, bytes: 10000 }, { key: "plugin", tokens: 500, bytes: 2000 },
] };
const used = 42000;
const window = 128000;
const budget = breakdown(used, window, saved);
equal(budget.categories.reduce((sum, category) => sum + category.tokens, 0), window);
equal(budget.categories[4].tokens, used - saved.fixed);
equal(budget.reserve, 16384);
const cells = squares(budget.categories, 200);
equal(cells.length, 200);
equal(cells.filter(cell => cell.group === "ContextTools").length, 3);
equal(cells.filter(cell => cell.group === "ContextReserve").length, 26);
equal(breakdown(4000, window, saved).attributed, false);
equal(breakdown(used, window, { ...saved, valid: false }).attributed, false);
equal(breakdown(used, 0, saved).categories.length, 5);
equal(squares(breakdown(0, 0, null).categories, 200).length, 0);
const overflow = breakdown(140000, window, saved);
equal(overflow.categories.at(-1)?.tokens, 0);
equal(overflow.categories.at(-2)?.tokens, 0);
equal(squares(overflow.categories, 200).length, 200);
equal(squares([{ label: "Small", tokens: 1, glyph: "■", group: "small" }, { label: "Free", tokens: 99999, glyph: "□", group: "free" }], 200).filter(cell => cell.group === "small").length, 0);
const stale = breakdown(used, window, { ...saved, valid: false, promptAvailable: true, tools: null });
equal(stale.categories.find(category => category.group === "ContextSkills")?.tokens, 2500);
equal(stale.categories.find(category => category.group === "ContextTools")?.tokens, 0);
equal(stale.categories.find(category => category.group === "ContextChat")?.tokens, used - saved.system);
equal(stale.categories.reduce((sum, category) => sum + category.tokens, 0), window);
equal(stale.attributed, false);
console.log("Context budget and square conservation passed.");
