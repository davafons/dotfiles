import type { Composer } from "yuke:ui";
import type { ChatView } from "yuke:chat";
import type { Position } from "./index.js";
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
    /** Normal transcript gf requests a file opener. Arguments are borrowed for synchronous dispatch only. */
    "vim-mode:open-file"(viewBorrow: ChatView, positionBorrow: Position): void;
    "composer-vim:mode"(composerBorrow: Composer, mode: Mode, previous: Mode): void;
  }
}
