//! Read typed feature switches from a plugin-owned settings file.
import { fs } from "yuke";

/** Read settings.json over defaults. Missing files use defaults; unknown keys, wrong types and invalid intervals throw. The caller owns the result. @template {Record<string, boolean | string | number>} T @param {import("yuke").Context} ctx @param {T} defaults @returns {Promise<T>} */
export async function readSettings(ctx, defaults) {
  const path = ctx.root + "/settings.json";
  if (!await fs.stat(path)) return { ...defaults };
  const raw = JSON.parse(await fs.readFile(path));
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new TypeError("settings.json must contain an object");
  for (const key of Object.keys(raw)) {
    if (!Object.hasOwn(defaults, key)) throw new TypeError("Unknown setting: " + key);
    const value = raw[key];
    if (typeof value !== typeof defaults[key]) throw new TypeError(key + " must be " + typeof defaults[key]);
    if (typeof value === "number" && (!Number.isSafeInteger(value) || value < 16 || value > 60000)) throw new TypeError(key + " must be an integer from 16 to 60000 milliseconds");
  }
  return { ...defaults, ...raw };
}
