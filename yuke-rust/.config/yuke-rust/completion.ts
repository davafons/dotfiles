import { type Mount, strokeOf, type Tui, type WidgetMount } from "yuke:tui";

/** A nonmodal completion list anchored to one composer. It never takes the focus. */
export class Completion<T> {
  readonly mount: Mount;
  readonly #items: readonly T[];
  #selected = 0;

  constructor(
    tui: Tui,
    source: WidgetMount,
    items: readonly T[],
    label: (item: T) => string,
    choose: (item: T) => void,
    cancel: () => void,
  ) {
    this.#items = items;
    const labels = items.map(label);
    const height = Math.min(6, items.length);
    this.mount = tui.overlay(
      () => ({
        draw: (canvas) => {
          const first = Math.max(0, this.#selected - canvas.height + 1);
          for (let row = 0; row < canvas.height; row += 1) {
            const index = first + row;
            const style = index === this.#selected ? "picker.selected" : "toast.body";
            canvas.fill(0, row, canvas.width, 1, style);
            canvas.text(0, row, labels[index] ?? "", style);
          }
        },
        key: (event) => {
          if (tui.focused !== source.widget) return false;
          const stroke = strokeOf(event);
          if (stroke === "up" || stroke === "ctrl+p") this.#selected = Math.max(0, this.#selected - 1);
          else if (stroke === "down" || stroke === "ctrl+n")
            this.#selected = Math.min(items.length - 1, this.#selected + 1);
          else if (stroke === "tab" || stroke === "enter") {
            const item = this.#items[this.#selected];
            if (item !== undefined) choose(item);
          } else if (stroke === "esc") cancel();
          else return false;
          return true;
        },
        mouse: (event) => {
          if (event.action !== "press" || event.button !== "left") return false;
          const first = Math.max(0, this.#selected - height + 1);
          const item = items[first + event.row];
          if (item !== undefined) choose(item);
          return true;
        },
      }),
      {
        modal: false,
        place: (size) => {
          const rect = source.rect;
          const rows = Math.min(height, Math.max(0, rect.row));
          return {
            column: rect.column,
            row: Math.max(0, rect.row - rows),
            width: Math.min(rect.width, size.width - rect.column),
            height: rows,
          };
        },
      },
    );
  }

  close(): void {
    this.mount.close();
  }
}
