import { ChatDocument, type ChatPresentation } from "yuke:chat";
import type { Frozen, PluginContext } from "yuke:plugins";
import type { SessionUpdate } from "yuke:protocol";
import type { Infer } from "yuke:tools";
import type { Transcript } from "yuke:transcript";
import { type TextDocument, type TextItem, type TextRow, wrap } from "yuke:tui";

export const optionsSchema = {
  type: "object",
  properties: {
    tokenSpeed: { type: "boolean" },
    phaseTimers: { type: "boolean" },
    stepTimers: { type: "boolean" },
    speedRefreshMs: { type: "integer", minimum: 16, maximum: 60_000 },
    timerRefreshMs: { type: "integer", minimum: 16, maximum: 60_000 },
  },
} as const;

interface Phase {
  readonly name: string;
  readonly start: number;
  end: number | undefined;
}
interface Round {
  readonly id: string;
  readonly start: number;
  end: number | undefined;
  characters: number;
  tokens: number | null;
  label: string;
  readonly phases: Phase[];
  readonly thoughts: Map<number, Phase>;
  tools: number;
}
interface Metrics {
  current: Round | undefined;
  last: Round | undefined;
  readonly saved: Map<number, Round>;
  readonly thoughts: Map<string, Phase>;
  revision: number;
}
const metrics = new Map<string, Metrics>();
const repaints = new Map<string, Set<() => void>>();

function phaseLabel(round: Round, now: number): string {
  return round.phases
    .map(
      (phase) =>
        `${phase.name} ${elapsed((phase.end ?? (phase.name === "tools" ? now : (round.end ?? now))) - phase.start)}`,
    )
    .join(" · ");
}

function timedTitle(text: string, width: number): readonly TextRow[] {
  const rows: TextRow[] = [];
  for (const row of wrap(text, Math.max(1, width - 2))) {
    const from = row.start;
    const to = row.end;
    rows.push({
      segments: [
        { text: " ", copy: false },
        { text: text.slice(from, to), style: "chat.title", source: { kind: "text", from, to } },
      ],
      join: row.soft ? "" : "\n",
    });
  }
  return rows;
}

/** Format an observed duration. The label does not imply a provider measurement. */
export function elapsed(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  if (seconds === 0) return "<1s";
  if (seconds < 60) return `${seconds}s`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds / 60) % 60;
  return `${hours === 0 ? "" : `${hours}h`}${minutes === 0 ? "" : `${minutes}m`}${seconds % 60 === 0 ? "" : `${seconds % 60}s`}`;
}

function transition(round: Round, name: string, now: number): void {
  const phase = round.phases.at(-1);
  if (phase?.name === name) return;
  if (phase !== undefined) phase.end = now;
  round.phases.push({ name, start: now, end: undefined });
}

class Presentation implements ChatPresentation {
  readonly #base: ChatDocument;
  readonly #id: string;
  readonly #options: PluginContext<Infer<typeof optionsSchema>>["options"];
  #source: TextDocument | undefined;
  #cached: TextDocument | undefined;
  #revision = -1;
  #second = -1;
  readonly #cards = new Map<string, { readonly text: string; readonly item: TextItem }>();
  readonly #thoughts = new Map<
    string,
    { readonly source: TextItem; readonly title: string; readonly item: TextItem }
  >();
  constructor(
    key: string,
    folds: Iterable<readonly [string, boolean]> | undefined,
    options: PluginContext<Infer<typeof optionsSchema>>["options"],
  ) {
    this.#base = new ChatDocument(key, folds);
    this.#id = key.slice("session:".length);
    this.#options = options;
  }
  get folds(): [string, boolean][] {
    return this.#base.folds;
  }
  toggle(transcript: Transcript, key: string): boolean {
    return this.#base.toggle(transcript, key);
  }
  toggleTools(transcript: Transcript): void {
    this.#base.toggleTools(transcript);
  }
  project(transcript: Transcript): TextDocument {
    const source = this.#base.project(transcript);
    const state = metrics.get(this.#id);
    const second =
      (state?.current !== undefined && state.current.end === undefined) || (state?.last?.tools ?? 0) > 0
        ? Math.floor(Date.now() / 1000)
        : 0;
    if (
      this.#cached !== undefined &&
      source === this.#source &&
      this.#revision === (state?.revision ?? -1) &&
      this.#second === second
    )
      return this.#cached;
    this.#source = source;
    this.#revision = state?.revision ?? -1;
    this.#second = second;
    this.#cached = this.decorate(source, state);
    return this.#cached;
  }
  private decorate(source: TextDocument, state: Metrics | undefined): TextDocument {
    if (state === undefined) return source;
    const now = Date.now();
    const items: TextItem[] = [];
    for (let index = 0; index < source.items.length; index += 1) {
      let item = source.items[index];
      if (item === undefined) continue;
      const thought = state.thoughts.get(item.id);
      if (this.#options.stepTimers !== false && thought !== undefined) {
        const title = `~${elapsed((thought.end ?? now) - thought.start)}`;
        const cached = this.#thoughts.get(item.id);
        if (cached?.source === item && cached.title === title) item = cached.item;
        else {
          const source = item;
          item = {
            ...item,
            sections: item.sections.map((section) => {
              if (section.kind !== "label") return section;
              const text = `${section.text} · ${title}`;
              return { ...section, text, render: (width) => timedTitle(text, width) };
            }),
          };
          this.#thoughts.set(item.id, { source, title, item });
        }
      }
      items.push(item);
      if (this.#options.phaseTimers === false) continue;
      const delimiter = item.id.indexOf(":");
      let number = delimiter < 1 ? -1 : 0;
      for (let at = 0; at < delimiter; at += 1) {
        const digit = item.id.charCodeAt(at) - 48;
        if (digit < 0 || digit > 9) {
          number = -1;
          break;
        }
        number = number * 10 + digit;
      }
      if (number < 0) continue;
      const next = source.items[index + 1];
      let same = next !== undefined && next.id.charCodeAt(delimiter) === 58;
      for (let at = 0; same && at < delimiter; at += 1) same = item.id.charCodeAt(at) === next?.id.charCodeAt(at);
      if (same) continue;
      const round = state.saved.get(number);
      if (round !== undefined) items.push(this.card(`${number}:observed`, round));
    }
    if (this.#options.phaseTimers !== false && state.current !== undefined)
      items.push(this.card(`observed:${state.current.id}`, state.current));
    return { id: source.id, items };
  }
  private card(key: string, round: Round): TextItem {
    const cached = this.#cards.get(key);
    if (cached?.text === round.label) return cached.item;
    const item: TextItem = { id: key, sections: [{ id: "timing", kind: "text", text: round.label }] };
    this.#cards.set(key, { text: round.label, item });
    return item;
  }
}

/** Show observed phases, reasoning clocks, and output speed. Provider output usage replaces the live character estimate. */
export function apply(ctx: PluginContext<Infer<typeof optionsSchema>>): (() => void) | undefined {
  const tui = ctx.get("tui");
  if (
    tui === undefined ||
    (ctx.options.tokenSpeed === false && ctx.options.phaseTimers === false && ctx.options.stepTimers === false)
  )
    return;
  const chat = ctx.get("chat");
  let cancelTick: (() => void) | undefined;
  const publish = (): void => {
    const view = tui.panes.active?.view;
    const id = view === undefined ? undefined : chat.session(view);
    const state = id === undefined ? undefined : metrics.get(id);
    const round = state?.current ?? state?.last;
    if (state?.current !== undefined) state.current.label = phaseLabel(state.current, Date.now());
    else if (state?.last !== undefined && state.last.tools > 0) state.last.label = phaseLabel(state.last, Date.now());
    if (ctx.options.tokenSpeed !== false) {
      const ms = round === undefined ? 0 : (round.end ?? Date.now()) - round.start;
      const tokens = round?.tokens ?? (round?.characters ?? 0) / 4;
      const text =
        round === undefined || ms <= 0 || tokens <= 0
          ? "— tok/s"
          : `${round.tokens === null ? "~" : ""}${((tokens * 1000) / ms).toFixed(1)} tok/s`;
      tui.status.set("speed", { text, side: "right", order: 12, priority: 20 });
    }
    cancelTick?.();
    cancelTick =
      (state?.current !== undefined && state.current.end === undefined) || (state?.last?.tools ?? 0) > 0
        ? tui.addTimer(Math.min(ctx.options.speedRefreshMs ?? 250, ctx.options.timerRefreshMs ?? 100), publish)
        : undefined;
    tui.requestFrame();
    if (id !== undefined)
      repaints.get(id)?.forEach((changed) => {
        changed();
      });
  };
  const record = (sessionId: string, update: Frozen<SessionUpdate>): void => {
    let state = metrics.get(sessionId);
    if (update.sessionUpdate === "draftStarted") {
      if (state === undefined) {
        state = { current: undefined, last: undefined, saved: new Map(), thoughts: new Map(), revision: 0 };
        metrics.set(sessionId, state);
      }
      const now = Date.now();
      state.current = {
        id: update.draftId,
        start: now,
        end: undefined,
        characters: 0,
        tokens: null,
        label: "waiting <1s",
        phases: [{ name: "waiting", start: now, end: undefined }],
        thoughts: new Map(),
        tools: 0,
      };
      state.revision += 1;
      publish();
      return;
    }
    if (state === undefined) return;
    const round = state.current;
    if (update.sessionUpdate === "model" && round !== undefined && round.id === update.draftId) {
      const event = update.event;
      const now = Date.now();
      if (event.kind === "blockStarted") {
        transition(
          round,
          event.content.kind === "reasoning"
            ? "thinking"
            : event.content.kind === "toolCall"
              ? "tool input"
              : "responding",
          now,
        );
        if (event.content.kind === "reasoning") {
          const thought = { name: "thought", start: now, end: undefined };
          round.thoughts.set(event.blockId, thought);
          state.thoughts.set(`draft:${round.id}:${event.blockId}`, thought);
        }
      } else if (event.kind === "blockStopped") {
        const thought = round.thoughts.get(event.blockId);
        if (thought !== undefined) thought.end = now;
      } else if (event.kind === "responseCompleted") {
        round.end = now;
        round.tokens = event.usage.output ?? null;
        const phase = round.phases.at(-1);
        if (phase !== undefined) phase.end = now;
      } else return;
      state.revision += 1;
    } else if (update.sessionUpdate === "draftCommitted" && round !== undefined && round.id === update.draftId) {
      round.end ??= Date.now();
      round.label = phaseLabel(round, round.end);
      state.last = round;
      state.saved.set(update.eventNumber, round);
      for (let index = 0; index < update.blocks.length; index += 1) {
        const block = update.blocks[index];
        if (block === undefined) continue;
        const thought = round.thoughts.get(block);
        if (thought !== undefined) {
          thought.end ??= round.end;
          state.thoughts.set(`${update.eventNumber}:${index}`, thought);
          state.thoughts.delete(`draft:${round.id}:${block}`);
        }
      }
      state.current = undefined;
      state.revision += 1;
    } else if (update.sessionUpdate === "toolStarted" || update.sessionUpdate === "toolFinished") {
      const called = state.saved.get(update.position.eventNumber);
      if (called === undefined) return;
      const now = Date.now();
      if (update.sessionUpdate === "toolStarted") {
        if (called.tools === 0) called.phases.push({ name: "tools", start: now, end: undefined });
        called.tools += 1;
      } else {
        called.tools = Math.max(0, called.tools - 1);
        if (called.tools === 0) {
          const phase = called.phases.at(-1);
          if (phase?.name === "tools") phase.end = now;
        }
      }
      called.label = phaseLabel(called, now);
      state.revision += 1;
    } else if (update.sessionUpdate === "draftDiscarded" || update.sessionUpdate === "roundFailed") {
      state.current = undefined;
      state.revision += 1;
    } else return;
    publish();
  };
  ctx.addListener("session.update", (event) => {
    const update = event.update;
    if (
      update.sessionUpdate === "model" &&
      (update.event.kind === "textDelta" ||
        update.event.kind === "reasoningDelta" ||
        update.event.kind === "refusalDelta" ||
        update.event.kind === "toolInputDelta")
    ) {
      const round = metrics.get(event.sessionId)?.current;
      if (round !== undefined && round.id === update.draftId) round.characters += update.event.text.length;
      return;
    }
    record(event.sessionId, update);
  });
  const stopPresentation = chat.setPresentation((options) => {
    const id = options.id.slice("session:".length);
    let changes = repaints.get(id);
    if (changes === undefined) {
      changes = new Set();
      repaints.set(id, changes);
    }
    changes.add(options.requestUpdate);
    const owned = changes;
    options.signal.addEventListener(
      "abort",
      () => {
        owned.delete(options.requestUpdate);
        if (owned.size === 0) repaints.delete(id);
      },
      { once: true },
    );
    return new Presentation(options.id, options.folds, ctx.options);
  });
  chat.addChangeListener(publish);
  tui.addFocusListener(publish);
  return () => {
    cancelTick?.();
    stopPresentation();
    metrics.clear();
    repaints.clear();
  };
}
