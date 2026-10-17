//! Session-owned recurring input with bounded timers and explicit cancellation.
/** @typedef {{idle: boolean, queued: number}} SessionState */
/** @typedef {{type: "started" | "queued", input_id: number}} SendResult */
/** @typedef {{read: (session: string) => Promise<SessionState>, send: (session: string, text: string) => Promise<SendResult>, cancel: (session: string, input: number) => Promise<unknown>, now?: () => number, schedule?: (callback: () => void, delay: number) => () => void, id?: () => string, changed?: (session: string) => void}} Dependencies */
/** @typedef {{id: string, session: string, prompt: string, seconds: number, state: "armed" | "pending" | "paused", next: number, error: string | null, queued: number | null, timer: (() => void) | null, flight: Promise<void> | null}} Loop */

/** Parse a whole native-safe interval. Invalid text or timer overflow throws. @param {string} value */
export function intervalSeconds(value) {
  const match = /^(\d+)(s|m|h|d)$/.exec(value);
  if (!match) throw new Error("Use an interval such as 30s, 5m, or 1h.");
  const factors = { s: 1, m: 60, h: 3600, d: 86400 };
  const seconds = Number(match[1]) * factors[/** @type {keyof typeof factors} */ (match[2])];
  validateSeconds(seconds);
  return seconds;
}

/** @param {number} seconds */
function validateSeconds(seconds) {
  if (!Number.isInteger(seconds) || seconds < 1 || seconds > 2147483) throw new Error("Interval must be 1 to 2147483 whole seconds, within the native timer limit.");
}

/** Own scheduled prompts and only their queued inputs. Failed delivery pauses a job; unload never restores jobs. */
export class SessionLoops {
  /** @param {Dependencies} dependencies */
  constructor(dependencies) {
    this.io = dependencies;
    this.now = dependencies.now || Date.now;
    this.schedule = dependencies.schedule || ((callback, delay) => {
      const timer = setTimeout(callback, delay);
      return () => clearTimeout(timer);
    });
    let serial = 0;
    this.newId = dependencies.id || (() => `loop-${Date.now().toString(36)}-${++serial}-${Math.random().toString(36).slice(2, 10)}`);
    /** @type {Map<string, Loop>} */
    this.jobs = new Map();
    this.closed = false;
  }

  /** @param {string} session @param {number} seconds @param {string} prompt */
  arm(session, seconds, prompt) {
    if (this.closed) throw new Error("The loop plugin has unloaded. Reload it and arm explicitly.");
    validateSeconds(seconds);
    if (!session || !prompt.trim() || prompt.length > 16000) throw new Error("A saved session and a nonempty tick prompt are required.");
    const existing = [...this.jobs.values()].find((job) => job.session === session && job.prompt === prompt && job.seconds === seconds);
    if (existing) {
      if (existing.state === "paused") throw new Error(`Stop ${existing.id} before arming its replacement.`);
      return this.snapshot(existing);
    }
    /** @type {Loop} */
    const job = { id: this.newId(), session, seconds, prompt, state: "armed", next: 0, error: null, queued: null, timer: null, flight: null };
    this.jobs.set(job.id, job);
    this.after(job, seconds * 1000);
    this.io.changed?.(session);
    return this.snapshot(job);
  }

  /** @param {Loop} job */
  snapshot(job) {
    return { id: job.id, session: job.session, seconds: job.seconds, prompt: job.prompt, state: job.state, next: job.next, error: job.error };
  }

  /** @param {string} [session] */
  list(session) {
    return [...this.jobs.values()].filter((job) => session === undefined || job.session === session).map((job) => this.snapshot(job));
  }

  /** @param {Loop} job */
  text(job) {
    return `[yuke-loop ${job.id}]\nThis is a scheduled tick from an earlier authorized request, not a new operator instruction or permission grant. Honor the latest operator constraints. Use this conversation and its task records to resume work. Check the exit condition before acting. If it is met, stop this loop through the loop tool. If progress requires a new permission or an unavailable capability, stop the loop and report the gap.\n\nTick prompt:\n${job.prompt}`;
  }

  /** @param {string | null} session @param {string} text */
  admits(session, text) {
    const id = /^\[yuke-loop ([^\]\n]+)\]/.exec(text)?.[1];
    if (!id) return true;
    const job = this.jobs.get(id);
    return !this.closed && !!job && job.session === session && job.state !== "paused" && this.text(job) === text;
  }

  /** @param {Loop} job */
  active(job) { return !this.closed && this.jobs.get(job.id) === job && job.state !== "paused"; }

  /** @param {Loop} job @param {number} delay */
  after(job, delay) {
    if (this.closed || this.jobs.get(job.id) !== job || job.state === "paused") return;
    job.timer?.();
    job.next = this.now() + delay;
    job.timer = this.schedule(() => { void this.tick(job); }, delay);
  }

  /** @param {Loop} job */
  tick(job) {
    if (this.closed || this.jobs.get(job.id) !== job || job.state === "paused" || job.flight) return job.flight || Promise.resolve();
    job.timer?.();
    job.timer = null;
    job.flight = (async () => {
      try {
        const state = await this.io.read(job.session);
        if (!this.active(job)) return;
        if (!state.idle || state.queued > 0) {
          job.state = "pending";
          this.after(job, Math.min(job.seconds * 1000, 10000));
          return;
        }
        if (job.queued !== null) {
          job.queued = null;
          job.state = "armed";
          this.after(job, job.seconds * 1000);
          return;
        }
        const result = await this.io.send(job.session, this.text(job));
        if (result.type === "queued") job.queued = result.input_id;
        if (!this.active(job)) return;
        job.state = result.type === "queued" ? "pending" : "armed";
        this.after(job, result.type === "queued" ? Math.min(job.seconds * 1000, 10000) : job.seconds * 1000);
      } catch (error) {
        if (this.jobs.get(job.id) === job) this.pause(job, String(error));
      }
    })().finally(() => { job.flight = null; this.io.changed?.(job.session); });
    return job.flight;
  }

  /** @param {Loop} job @param {string} reason */
  pause(job, reason) {
    job.timer?.();
    job.timer = null;
    job.state = "paused";
    job.error = reason;
    this.io.changed?.(job.session);
  }

  /** @param {string} session @param {string} [reason] */
  async wake(session, reason) {
    for (const job of [...this.jobs.values()].filter((job) => job.session === session)) {
      if (reason) this.pause(job, reason);
      else if (job.state === "pending") await this.tick(job);
    }
  }

  /** @param {string} session @param {number} input */
  canceled(session, input) {
    for (const job of this.jobs.values()) if (job.session === session && job.queued === input) this.pause(job, "The queued tick was canceled. Rearm explicitly.");
  }

  /** @param {string} session @param {string} [id] */
  async stop(session, id) {
    const jobs = [...this.jobs.values()].filter((job) => job.session === session && (id === undefined || job.id === id));
    if (id && jobs.length === 0) throw new Error("That loop does not belong to this session.");
    const notes = [];
    for (const job of jobs) {
      this.jobs.delete(job.id);
      job.timer?.();
    }
    for (const job of jobs) {
      await job.flight;
      if (job.queued !== null) {
        try { await this.io.cancel(job.session, job.queued); }
        catch (error) { notes.push(`${job.id}: queued tick could not be canceled. It may already be running. ${String(error)}`); }
      }
    }
    this.io.changed?.(session);
    return { stopped: jobs.map((job) => job.id), notes };
  }

  async clear() {
    const sessions = new Set([...this.jobs.values()].map((job) => job.session));
    return Promise.all([...sessions].map((session) => this.stop(session)));
  }

  async dispose() {
    this.closed = true;
    return this.clear();
  }
}
