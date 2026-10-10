import type { Tui } from "yuke:ui";
declare module "yuke" {
  interface Events {
    "prompt-history:control-key"(event: Parameters<Tui["keymap"]["onKey"]>[0]): boolean;
  }
}
export {};
