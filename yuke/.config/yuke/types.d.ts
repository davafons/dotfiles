import type { Context } from "yuke";
import type { Tui } from "yuke:ui";
/** Borrowed plugin and TUI owners. A view must not retain either after close. */
export interface UiBorrow { ctx: Context; tui: Tui; }
