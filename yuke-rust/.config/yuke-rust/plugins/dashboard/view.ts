import { type Canvas, fit, type MouseEvent, measure, type View } from "yuke:tui";

const LOGO = [
  "██╗   ██╗██╗   ██╗██╗  ██╗███████╗",
  "╚██╗ ██╔╝██║   ██║██║ ██╔╝██╔════╝",
  " ╚████╔╝ ██║   ██║█████╔╝ █████╗  ",
  "  ╚██╔╝  ██║   ██║██╔═██╗ ██╔══╝  ",
  "   ██║   ╚██████╔╝██║  ██╗███████╗",
  "   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝",
];
const COMPACT_LOGO = ["YUKE"];

interface Action {
  readonly label: string;
  readonly key: string;
  readonly command: string;
}
interface DrawText {
  readonly text: string;
  readonly column: number;
  readonly row: number;
  readonly style: string;
}

/** The original dashboard layout. Geometry and clipped text change only with size or model context. */
export class Dashboard implements View {
  readonly #actions: readonly Action[];
  readonly #workspace: string;
  readonly #activate: (command: string) => void;
  readonly #rows: DrawText[] = [];
  #model = "no model yet";
  #width = -1;
  #height = -1;
  #menuColumn = 0;
  #menuRow = 0;
  #menuWidth = 0;
  #menuCount = 0;

  constructor(actions: readonly Action[], workspace: string, activate: (command: string) => void) {
    this.#actions = actions;
    this.#workspace = workspace;
    this.#activate = activate;
  }

  /** Refresh the displayed model after a status change. */
  model(text: string): void {
    if (text === this.#model) return;
    this.#model = text;
    this.#width = -1;
  }

  draw(canvas: Canvas): void {
    if (canvas.width !== this.#width || canvas.height !== this.#height) this.#build(canvas.width, canvas.height);
    for (let index = 0; index < this.#rows.length; index += 1) {
      const line = this.#rows[index];
      if (line !== undefined) canvas.text(line.column, line.row, line.text, line.style);
    }
  }

  mouse(event: MouseEvent): boolean {
    if (event.action !== "press" || event.button !== "left") return false;
    const row = event.row - this.#menuRow;
    const column = event.column - this.#menuColumn;
    if (row < 0 || row >= this.#menuCount || column < 0 || column >= this.#menuWidth) return false;
    const action = this.#actions[row];
    if (action === undefined) return false;
    this.#activate(action.command);
    return true;
  }

  #build(width: number, height: number): void {
    this.#width = width;
    this.#height = height;
    this.#rows.length = 0;
    this.#menuCount = 0;
    if (width <= 0 || height <= 0) return;
    const contentWidth = Math.min(54, width);
    const left = Math.floor((width - contentWidth) / 2);
    const count = this.#actions.length;
    const logo = width >= 40 && height >= count + 14 ? LOGO : COMPACT_LOGO;
    const details = height >= logo.length + count + 6;
    const footer = height >= logo.length + count + 3;
    const used = logo.length + 1 + (details ? 3 : 0) + count + (footer ? 2 : 0);
    let row = Math.max(0, Math.floor((height - used) / 2));
    for (let index = 0; index < logo.length && row < height; index += 1) {
      this.#center(logo[index] ?? "", left, row, contentWidth, "dashboard.logo");
      row += 1;
    }
    row += 1;
    if (details) {
      this.#center(this.#workspace, left, row, contentWidth, "dashboard.context");
      this.#center(this.#model, left, row + 1, contentWidth, "dashboard.context");
      row += 3;
    }
    this.#menuColumn = left;
    this.#menuRow = row;
    this.#menuWidth = contentWidth;
    for (let index = 0; index < count && row < height; index += 1) {
      const action = this.#actions[index];
      if (action === undefined) continue;
      const keyWidth = measure(action.key);
      this.#rows.push({
        text: this.#clip(action.label, Math.max(0, contentWidth - keyWidth - 2)),
        column: left,
        row,
        style: "dashboard.action",
      });
      this.#rows.push({ text: action.key, column: left + contentWidth - keyWidth, row, style: "dashboard.key" });
      this.#menuCount += 1;
      row += 1;
    }
    if (footer && row + 1 < height)
      this.#center("unleash your harness", left, row + 1, contentWidth, "dashboard.context");
  }

  #center(text: string, left: number, row: number, width: number, style: string): void {
    const shown = this.#clip(text, width);
    this.#rows.push({ text: shown, column: left + Math.floor((width - measure(shown)) / 2), row, style });
  }

  #clip(text: string, width: number): string {
    if (width <= 0) return "";
    return measure(text) <= width ? text : `${text.slice(0, fit(text, width - 1))}…`;
  }
}
