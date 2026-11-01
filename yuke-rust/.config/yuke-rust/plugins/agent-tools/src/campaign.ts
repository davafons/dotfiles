import { mkdir, writeTextFile } from "yuke:fs";
import type { PluginContext, SessionContext } from "yuke:plugins";
import { env } from "yuke:process";

interface Grant {
  readonly slots: number;
  readonly deadline_ms: number;
  readonly nonce: string;
  readonly workspace: string;
  readonly home: string;
  readonly max_concurrent: number;
}
const ALLOWED = new Set(["read", "write", "edit", "spawn_agent", "send_agent_input", "stop"]);

/** Enforce the existing prepaid campaign grant only when its environment variable is present. */
export class Campaign {
  private readonly enabled: boolean;
  private readonly grant: Grant | undefined;
  private readonly failure: unknown;
  private root: string | undefined;
  private reserved = 1;
  private readonly children = new Set<string>();
  private readonly rounds = new Map<string, number>();

  constructor() {
    const raw = env.get("DAVSTACK_CAMPAIGN");
    this.enabled = raw !== undefined;
    if (raw === undefined) return;
    try {
      const value: unknown = JSON.parse(raw);
      if (
        typeof value !== "object" ||
        value === null ||
        !("slots" in value) ||
        typeof value.slots !== "number" ||
        !Number.isInteger(value.slots) ||
        value.slots < 1 ||
        value.slots > 12 ||
        !("deadline_ms" in value) ||
        typeof value.deadline_ms !== "number" ||
        !Number.isInteger(value.deadline_ms) ||
        value.deadline_ms <= Date.now() ||
        value.deadline_ms > Date.now() + 60_000 ||
        !("nonce" in value) ||
        typeof value.nonce !== "string" ||
        !/^[a-f0-9]{32}$/.test(value.nonce) ||
        !("workspace" in value) ||
        typeof value.workspace !== "string" ||
        !value.workspace.startsWith("/") ||
        !("home" in value) ||
        typeof value.home !== "string" ||
        !value.home.startsWith("/") ||
        !("max_concurrent" in value) ||
        typeof value.max_concurrent !== "number" ||
        !Number.isInteger(value.max_concurrent) ||
        value.max_concurrent < 1 ||
        value.max_concurrent > 12
      )
        throw new Error("Invalid campaign grant.");
      this.grant = value as Grant;
    } catch (error) {
      this.failure = error;
    }
  }

  async ready(ctx: PluginContext): Promise<void> {
    if (!this.enabled || this.grant === undefined) return;
    const cache = env.get("XDG_CACHE_HOME");
    if (cache === undefined) throw new Error("A campaign needs XDG_CACHE_HOME.");
    await mkdir(cache, { recursive: true, mode: 0o700 });
    await writeTextFile(`${cache}/campaign-ready.json`, JSON.stringify(this.grant), {
      mode: 0o600,
      signal: ctx.signal,
    });
  }

  private check(): Grant {
    if (this.failure !== undefined) throw this.failure;
    if (this.grant === undefined) throw new Error("Missing campaign grant.");
    if (Date.now() >= this.grant.deadline_ms) throw new Error("Campaign deadline reached.");
    return this.grant;
  }

  reserve(parent: SessionContext, active: number): void {
    if (!this.enabled) return;
    const grant = this.check();
    if (parent.parent !== undefined || (this.root !== undefined && parent.sessionId !== this.root))
      throw new Error("Only the campaign root can delegate.");
    if (this.reserved >= grant.slots) throw new Error("Campaign session quota exhausted.");
    if (active >= grant.max_concurrent) throw new Error("Campaign concurrent-session limit reached.");
    this.reserved += 1;
  }

  created(id: string): void {
    if (this.enabled) this.children.add(id);
  }

  attach(s: SessionContext): void {
    if (!this.enabled) return;
    s.hook("prompt.build", (event) => ({
      sections: {
        ...event.sections,
        campaign:
          "This is a bounded campaign. Only read, write, edit, spawn_agent, send_agent_input, and stop may run. File operations stay in the private campaign workspace. Each session has at most eight rounds. Do not delegate from a child.",
      },
    }));
    s.hook("round.before", () => {
      const grant = this.check();
      if (s.folder !== grant.workspace) throw new Error("Campaign workspace mismatch.");
      if (s.parent === undefined) {
        if (this.root !== undefined && this.root !== s.sessionId)
          throw new Error("Only one prepaid root session is allowed.");
        this.root = s.sessionId;
      } else if (s.parent !== this.root || !this.children.has(s.sessionId))
        throw new Error("Session has no prepaid campaign slot.");
      const count = (this.rounds.get(s.sessionId) ?? 0) + 1;
      if (count > 8) throw new Error("Campaign session round quota exhausted.");
      this.rounds.set(s.sessionId, count);
      console.log("CAMPAIGN_REQUEST", JSON.stringify({ session: s.sessionId, count, reserved: this.reserved }));
      return { tools: [...ALLOWED].filter((name) => s.parent === undefined || name !== "spawn_agent") };
    });
    s.hook("tool.before", (event) => {
      const grant = this.check();
      if (!ALLOWED.has(event.call.name)) return { block: "Tool is not allowed in a bounded campaign." };
      if (s.parent !== undefined && event.call.name === "spawn_agent")
        return { block: "Nested campaign delegation is not allowed." };
      if (event.call.name === "read" || event.call.name === "write" || event.call.name === "edit") {
        const args = event.call.arguments;
        if (
          typeof args !== "object" ||
          args === null ||
          !("path" in args) ||
          typeof args.path !== "string" ||
          args.path.includes("\0")
        )
          return { block: "Campaign tool requires a workspace path." };
        let path = args.path;
        if (path.startsWith("~/")) path = grant.home + path.slice(1);
        if (event.call.name === "read" && path.startsWith(`${grant.home}/.agents/skills/`))
          path = grant.workspace + path.slice(grant.home.length);
        if (!path.startsWith("/")) path = `${grant.workspace}/${path}`;
        const parts: string[] = [];
        for (const part of path.split("/")) {
          if (part === "..") parts.pop();
          else if (part !== "" && part !== ".") parts.push(part);
        }
        path = `/${parts.join("/")}`;
        if (path !== grant.workspace && !path.startsWith(`${grant.workspace}/`))
          return { block: "Campaign file access must stay in the private workspace." };
      }
      return undefined;
    });
  }
}
