import { stat } from "yuke:fs";
import type { PluginContext, SessionContext } from "yuke:plugins";
import { stdio } from "../../stdio.ts";
import { install } from "./direct.ts";

interface Result {
  stdout: string;
  stderr: string;
  exit_code: number | null;
  signal: number | null;
  timed_out: boolean;
  canceled: boolean;
}
let busy = false;

/** Carry passwords only through the private socket and stdin. The helper bounds and redacts output before return. */
export async function run(
  argv: readonly string[],
  cwd: string,
  timeout: number,
  signal: AbortSignal,
  password: (attempt: number) => Promise<string | undefined>,
): Promise<Result> {
  if (busy) throw new Error("Another sudo request is active.");
  busy = true;
  const secrets: string[] = [];
  try {
    let secret = await password(1);
    if (secret === undefined || secret === "") throw new Error("Password entry canceled. No command ran.");
    const check = (value: string): void => {
      if (value.length > 4096 || /[\r\n\x00]/u.test(value))
        throw new Error("Use a one-line password of at most 4096 characters.");
    };
    check(secret);
    secrets.push(secret);
    return await stdio(
      ["python3", `${import.meta.dirname}/../../helpers/sudo-command.py`],
      cwd,
      signal,
      async (connection) => {
        await connection.write(`${JSON.stringify({ argv, password: secret, timeout_ms: timeout })}\n`);
        secret = "";
        let buffered = "",
          result: Result | undefined,
          attempt = 1;
        for (;;) {
          const event = await connection.read();
          if ("code" in event) {
            if (result === undefined)
              throw new Error("Sudo ended without a result. Do not rerun the command to repair this receipt.");
            for (const value of secrets) {
              result.stdout = result.stdout.replaceAll(value, "[REDACTED]");
              result.stderr = result.stderr.replaceAll(value, "[REDACTED]");
            }
            return result;
          }
          if (event.stream === "stderr") continue;
          buffered += event.text;
          if (buffered.length > 128 * 1024) throw new Error("Sudo returned an oversized private record.");
          for (;;) {
            const end = buffered.indexOf("\n");
            if (end < 0) break;
            const message: unknown = JSON.parse(buffered.slice(0, end));
            buffered = buffered.slice(end + 1);
            if (typeof message !== "object" || message === null || !("type" in message))
              throw new Error("Invalid sudo record.");
            if (
              message.type === "result" &&
              "result" in message &&
              typeof message.result === "object" &&
              message.result !== null
            ) {
              const value = message.result;
              if (
                !("stdout" in value) ||
                typeof value.stdout !== "string" ||
                !("stderr" in value) ||
                typeof value.stderr !== "string" ||
                !("exit_code" in value) ||
                (value.exit_code !== null && typeof value.exit_code !== "number") ||
                !("signal" in value) ||
                (value.signal !== null && typeof value.signal !== "number") ||
                !("timed_out" in value) ||
                typeof value.timed_out !== "boolean" ||
                !("canceled" in value) ||
                typeof value.canceled !== "boolean"
              )
                throw new Error("Invalid sudo result.");
              result = value as Result;
            } else if (
              message.type === "password" &&
              "attempt" in message &&
              message.attempt === attempt + 1 &&
              result === undefined
            ) {
              attempt += 1;
              const next = await password(attempt);
              if (next !== undefined) check(next);
              if (next !== undefined && next !== "") secrets.push(next);
              await connection.write(`${JSON.stringify({ password: next ?? "" })}\n`);
            } else throw new Error("Invalid sudo event.");
          }
        }
      },
    );
  } finally {
    secrets.length = 0;
    busy = false;
  }
}

/** Register a root command tool. Each execution needs local approval and masked entry; headless calls run nothing. */
export function session(s: SessionContext): undefined {
  s.tools.define({
    name: "sudo_command",
    description:
      "Request one root command. Supply an absolute executable and separate arguments. Explain why root is needed. The user approves each command and enters its password in a masked local field. Never request a password in chat or tool arguments. Stdin is closed. Password retries stay in this call. Do not restart a rejected or canceled command without user permission.",
    concurrency: "serial",
    parameters: {
      type: "object",
      additionalProperties: false,
      properties: {
        argv: { type: "array", items: { type: "string" } },
        reason: { type: "string" },
        cwd: { type: "string" },
        timeout_ms: { type: "integer", minimum: 1, maximum: 600_000 },
      },
      required: ["argv", "reason"],
    },
    execute: async (args, context) => {
      if (
        args.argv.length === 0 ||
        args.argv.length > 128 ||
        !args.argv[0]?.startsWith("/") ||
        args.argv.some((value) => value.includes("\0"))
      )
        throw new Error("Supply one absolute executable and up to 127 literal arguments.");
      if (!args.reason.trim() || args.reason.length > 1000 || /[\x00-\x1f\x7f]/u.test(args.reason))
        throw new Error("Explain why root is needed, without control characters.");
      if (args.cwd !== undefined && (!args.cwd || args.cwd.length > 8192 || /[\x00-\x1f\x7f]/u.test(args.cwd)))
        throw new Error("Invalid working directory.");
      const cwd =
        args.cwd === undefined ? context.folder : args.cwd.startsWith("/") ? args.cwd : `${context.folder}/${args.cwd}`;
      if (!(await stat(cwd, { signal: context.signal })).isDirectory)
        throw new Error("The working directory is not a directory.");
      const approved = await s.ask(
        {
          questions: [
            {
              id: "approve",
              header: "Run as root?",
              question: `${args.reason}\n\nExecutable and literal arguments:\n${JSON.stringify(args.argv)}\n\nDirectory: ${cwd}\nDeadline: ${args.timeout_ms ?? 120_000} ms\nOutput goes to the model.`,
              options: [{ label: "Do not run" }, { label: "Run as root" }],
            },
          ],
        },
        { signal: context.signal },
      );
      if (approved?.[0]?.values[0] !== "Run as root")
        return { text: "Sudo declined or canceled. No command ran.", isError: true };
      const result = await run(args.argv, cwd, args.timeout_ms ?? 120_000, context.signal, async (attempt) => {
        const answers = await s.ask(
          {
            questions: [
              {
                id: "password",
                header: "Sudo password · local only",
                question:
                  attempt === 1
                    ? "Enter your sudo password."
                    : `Password not accepted. Try again (attempt ${attempt}).`,
                options: [],
                other: true,
                secret: true,
              },
            ],
          },
          { signal: context.signal },
        );
        return answers?.[0]?.other ?? undefined;
      });
      return { text: JSON.stringify(result), isError: result.exit_code !== 0 || result.timed_out || result.canceled };
    },
  });
}

/** Add direct shell commands only to the terminal composer. */
export function apply(ctx: PluginContext): undefined {
  const tui = ctx.get("tui");
  if (tui !== undefined) install(ctx, tui);
}
