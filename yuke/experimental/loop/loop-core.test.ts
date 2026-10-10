import { describe, expect, test } from "bun:test";
import { intervalSeconds, SessionLoops } from "./loop-core.js";

async function settle() { for (let i = 0; i < 10; i++) await Promise.resolve(); }

function fixture() {
  let now = 0, serial = 0, timerId = 0;
  const timers = new Map<number, { at: number; callback: () => void }>();
  const sent: { session: string; text: string }[] = [];
  const canceled: { session: string; input: number }[] = [];
  let state = { idle: true, queued: 0 };
  let cancelError: string | null = null;
  let result: { type: "started" | "queued"; input_id: number } = { type: "started", input_id: 1 };
  const loops = new SessionLoops({
    now: () => now, id: () => `loop-${++serial}`,
    schedule(callback, delay) { const id = ++timerId; timers.set(id, { at: now + delay, callback }); return () => { timers.delete(id); }; },
    read: async () => state,
    send: async (session, text) => { sent.push({ session, text }); return result; },
    cancel: async (session, input) => { canceled.push({ session, input }); if (cancelError) throw new Error(cancelError); },
  });
  return { loops, sent, canceled,
    state: (value: typeof state) => { state = value; },
    cancelError: (value: string) => { cancelError = value; },
    result: (value: typeof result) => { result = value; },
    async advance(ms: number) {
      const end = now + ms;
      while (true) {
        const next = [...timers].sort((a, b) => a[1].at - b[1].at)[0];
        if (!next || next[1].at > end) break;
        now = next[1].at; timers.delete(next[0]); next[1].callback(); await settle();
      }
      now = end; await settle();
    },
  };
}

describe("session-bound scheduled turns", () => {
  test("parses durations and rejects native timer overflow or invalid intervals", () => {
    expect(intervalSeconds("5m")).toBe(300);
    expect(intervalSeconds("1h")).toBe(3600);
    for (const value of ["0s", "-1s", "30d", "5", "1.5m", "NaN", "999999999999999999h"]) expect(() => intervalSeconds(value)).toThrow();
  });

  test("stays inactive until armed, waits one interval, and sends into the same session", async () => {
    const f = fixture();
    await f.advance(5000); expect(f.sent).toEqual([]);
    const job = f.loops.arm("parent", 2, "Check CI. Stop at merge-ready.");
    await f.advance(1999); expect(f.sent).toEqual([]);
    await f.advance(1);
    expect(f.sent).toHaveLength(1);
    expect(f.sent[0].session).toBe("parent");
    expect(f.sent[0].text).toContain("Check CI. Stop at merge-ready.");
    expect(f.sent[0].text).toContain("not a new operator instruction or permission grant");
    expect(f.loops.admits("parent", f.sent[0].text)).toBe(true);
    expect(f.loops.admits("other", f.sent[0].text)).toBe(false);
    expect(f.loops.arm("parent", 2, job.prompt).id).toBe(job.id);
    await f.advance(2000); expect(f.sent).toHaveLength(2);
    await f.loops.dispose();
  });

  test("collapses busy ticks and respects unrelated queued user input", async () => {
    const f = fixture(); f.state({ idle: false, queued: 0 });
    f.loops.arm("parent", 1, "Probe the goal.");
    await f.advance(6000); expect(f.sent).toEqual([]);
    expect(f.loops.list("parent")[0].state).toBe("pending");
    f.state({ idle: true, queued: 1 }); await f.loops.wake("parent"); expect(f.sent).toEqual([]);
    f.state({ idle: true, queued: 0 }); await f.loops.wake("parent"); expect(f.sent).toHaveLength(1);
    await f.loops.wake("parent"); expect(f.sent).toHaveLength(1);
    await f.loops.dispose();
  });

  test("an admission race retains only its own queued tick and does not build a backlog", async () => {
    const f = fixture(); f.result({ type: "queued", input_id: 17 });
    f.loops.arm("parent", 1, "Monitor the predicate.");
    await f.advance(1000); expect(f.sent).toHaveLength(1);
    f.state({ idle: false, queued: 2 }); await f.advance(5000); expect(f.sent).toHaveLength(1);
    f.state({ idle: true, queued: 0 }); await f.loops.wake("parent"); expect(f.sent).toHaveLength(1);
    f.result({ type: "started", input_id: 18 }); await f.advance(1000); expect(f.sent).toHaveLength(2);
    await f.loops.dispose();
  });

  test("stop cancels only an owned queued input and preserves other sessions", async () => {
    const f = fixture(); f.result({ type: "queued", input_id: 17 });
    const a = f.loops.arm("a", 1, "Monitor A.");
    const b = f.loops.arm("b", 20, "Monitor B.");
    await f.advance(1000);
    await expect(f.loops.stop("b", a.id)).rejects.toThrow("does not belong");
    expect((await f.loops.stop("a", a.id)).stopped).toEqual([a.id]);
    expect(f.canceled).toEqual([{ session: "a", input: 17 }]);
    expect(f.loops.list("b").map((job) => job.id)).toEqual([b.id]);
    expect(f.loops.admits("a", f.sent[0].text)).toBe(false);
    await f.loops.dispose();
  });

  test("reports a queued cancellation that the engine refuses instead of clearing the queue", async () => {
    const f = fixture(); f.result({ type: "queued", input_id: 17 }); f.cancelError("already running");
    const job = f.loops.arm("a", 1, "Wait."); await f.advance(1000);
    const result = await f.loops.stop("a", job.id);
    expect(result.stopped).toEqual([job.id]);
    expect(result.notes[0]).toContain("already running");
    expect(f.canceled).toEqual([{ session: "a", input: 17 }]);
    expect(f.loops.list()).toEqual([]); await f.advance(5000); expect(f.sent).toHaveLength(1);
    await f.loops.dispose();
  });

  test("disposal clears all timers and requires explicit rearming in a new instance", async () => {
    const f = fixture(); f.loops.arm("a", 1, "A."); f.loops.arm("b", 2, "B.");
    await f.loops.dispose(); await f.advance(10000);
    expect(f.sent).toEqual([]); expect(f.loops.list()).toEqual([]);
    expect(() => f.loops.arm("a", 1, "Again.")).toThrow("unloaded");
    const next = fixture(); await next.advance(10000); expect(next.sent).toEqual([]);
    await next.loops.dispose();
  });

  test("stop during an asynchronous state read cannot send a later tick", async () => {
    let release!: (value: { idle: boolean; queued: number }) => void;
    const waiting = new Promise<{ idle: boolean; queued: number }>((resolve) => { release = resolve; });
    let callback = () => {}; const sent: string[] = [];
    const loops = new SessionLoops({ read: () => waiting, send: async (_, text) => { sent.push(text); return { type: "started", input_id: 1 }; }, cancel: async () => {}, schedule: (run) => { callback = run; return () => {}; } });
    const job = loops.arm("a", 1, "Probe."); callback();
    const stop = loops.stop("a", job.id);
    release({ idle: true, queued: 0 }); await stop;
    expect(sent).toEqual([]); await loops.dispose();
  });

  test("delivery failures pause rather than schedule more model requests", async () => {
    let callback = () => {}; let sends = 0;
    const loops = new SessionLoops({ read: async () => ({ idle: true, queued: 0 }), send: async () => { sends++; throw new Error("session missing"); }, cancel: async () => {}, schedule: (run) => { callback = run; return () => {}; } });
    loops.arm("a", 1, "Probe."); callback(); await settle();
    expect(loops.list("a")[0]).toMatchObject({ state: "paused", error: "Error: session missing" });
    await loops.wake("a"); expect(sends).toBe(1); await loops.dispose();
  });
});
