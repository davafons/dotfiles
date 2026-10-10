import type { Composer } from "yuke:ui";
/** Modes of the one composer editor. Replace mode is not supported. */
export type Mode = "insert" | "normal" | "visual" | "visual-line";
declare module "yuke" {
  interface Capabilities {
    "composer-vim": {
      mode(composerBorrow: Composer | null): Mode | "";
      setMode(composerBorrow: Composer, mode: Mode): void;
      cancel(composerBorrow: Composer): void;
      pending(composerBorrow: Composer): boolean;
    };
  }
  interface Events {
    "composer-vim:mode"(composerBorrow: Composer, mode: Mode, previous: Mode): void;
  }
}
