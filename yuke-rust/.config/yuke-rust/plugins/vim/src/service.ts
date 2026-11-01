import type { TextEditor } from "yuke:tui";

export type Mode = "insert" | "normal" | "visual" | "visual-line";

export interface ComposerVim {
  mode: (editor: TextEditor | null) => Mode | "";
  setMode: (editor: TextEditor, mode: "insert" | "normal") => void;
  cancel: (editor: TextEditor) => void;
  pending: (editor: TextEditor) => boolean;
  onMode: (listener: (editor: TextEditor, mode: Mode) => void) => () => void;
}

declare module "yuke:plugins" {
  interface Services {
    readonly "composer-vim": ComposerVim | undefined;
  }
}
