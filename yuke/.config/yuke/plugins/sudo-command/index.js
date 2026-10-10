//! Run direct composer commands and approved sudo. Passwords enter only a masked local prompt.
import { client, env, exec, lines, spawn } from "yuke";
import { openDetails } from "yuke:chat";
import { Session, currentPane } from "yuke:session";
/** @import { Context, CancellationSignal } from "yuke" */
/** @typedef {{ session: Session, composer: Composer, command: string, context: ReturnType<Context["resources"]>, owner: ReturnType<Context["resources"]>, started: boolean }} OwnedCommand */
/** @import { Composer } from "yuke:ui" */

/** @param {string} value */
function quote(value) { return "'" + value.replaceAll("'", "'\\''") + "'"; }
/** Register the migrated sudo-command operations. The plugin owns registrations; host failures throw. @param {import("yuke").Context} parent */
export default function(parent) {

    let busy = false;
    const tool = {
      name: "sudo_command",
      description: "Request one command as root. Supply an absolute executable path and separate arguments, not a shell command or a sudo prefix. Explain why root is needed. The user must approve each command and enter the password in a masked local dialog; never ask for a password in chat or tool arguments. Returns stdout, stderr, exit code, signal, and timeout status. Stdin is closed; this tool does not support interactive programs. Password retries stay in this call and follow sudo's attempt limit. Do not restart a rejected or canceled command without the user's permission.",
      parameters: {
        type: "object",
        properties: {
          argv: { type: "array", minItems: 1, maxItems: 128, items: { type: "string" }, description: "Absolute executable path followed by its arguments." },
          reason: { type: "string", minLength: 1, maxLength: 1000, description: "Why this command needs root." },
          cwd: { type: "string", description: "Working directory, relative to the workspace or absolute. Defaults to the workspace." },
          timeout_ms: { type: "integer", minimum: 1, maximum: 600000, description: "Execution deadline in milliseconds. Default 120000." },
        },
        required: ["argv", "reason"],
        additionalProperties: false,
      },
      /** @param {unknown} args @param {CancellationSignal} signal @param {{ workspaceRoot: string }} toolCtx */
      async execute(args, signal, toolCtx) {
        if (!args || typeof args !== "object" || Array.isArray(args)) throw new Error("Provide command arguments.");
        const value = /** @type {Record<string, unknown>} */ (args);
        if (Object.keys(value).some(key => !["argv", "reason", "cwd", "timeout_ms"].includes(key))) throw new Error("Unknown sudo argument. Never supply a password here.");
        if (!Array.isArray(value.argv) || !value.argv.length || value.argv.length > 128 ||
            value.argv.some(arg => typeof arg !== "string" || arg.length > 8192 || /[\x00-\x1f\x7f]/u.test(arg)) ||
            !value.argv[0].startsWith("/")) throw new Error("Use an absolute executable path and at most 128 arguments without control codes.");
        const argv = /** @type {string[]} */ (value.argv).slice();
        if (JSON.stringify(argv).length > 65536) throw new Error("Command arguments are too large.");
        if (typeof value.reason !== "string" || !value.reason.trim() || value.reason.length > 1000 || /[\x00-\x1f\x7f]/u.test(value.reason)) throw new Error("Explain why root is needed, without control codes.");
        if (value.cwd !== undefined && (typeof value.cwd !== "string" || !value.cwd || value.cwd.length > 8192 || /[\x00-\x1f\x7f]/u.test(value.cwd))) throw new Error("Use a nonempty working directory without control codes.");
        const timeoutMs = value.timeout_ms === undefined ? 120000 : value.timeout_ms;
        if (typeof timeoutMs !== "number" || !Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 600000) throw new Error("Use a deadline from 1 to 600000 milliseconds.");
        if (!parent.interaction.interactive) throw new Error("Sudo requires the Yuke TUI. No command ran.");
        if (busy) throw new Error("Another sudo request is active. Wait for it to finish.");
        if (signal.aborted || !parent.alive) throw new Error("Sudo request canceled. No command ran.");
        busy = true;
        let password = "";
        /** @type {string[]} */
        const passwords = [];
        try {
          const cwd = /** @type {string | undefined} */ (value.cwd);
          const approved = await parent.interaction.confirm("Run as root?", [
            value.reason, "", "Executable and arguments (no shell expansion):", JSON.stringify(argv),
            "", "Workspace: " + toolCtx.workspaceRoot, "Directory: " + (cwd ?? "."),
            "Deadline: " + timeoutMs + " ms", "", "The command can change system files. Its output goes to the model.",
          ].join("\n"), { signal, labels: { accept: "Run as root", cancel: "Do not run" } });
          if (approved !== true || signal.aborted || !parent.alive) return { output: "Sudo request declined or canceled. No command ran.", is_error: true };
          password = await parent.interaction.input("Sudo password (local only)", "Password", { signal, secret: true }) ?? "";
          if (!password || signal.aborted || !parent.alive) return { output: "Sudo password entry canceled. No command ran.", is_error: true };
          if (password.length > 4096 || /[\r\n\x00]/u.test(password)) throw new Error("Password entry must be one line of at most 4096 characters. No command ran.");
          passwords.push(password);
          const config = env.get("XDG_CONFIG_HOME") || (env.get("HOME") + "/.config");
          const helper = config + "/" + (env.get("YUKE_APPNAME") || "yuke") + "/plugins/sudo-command.py";
          const child = spawn(["python3", helper], { workspaceRoot: toolCtx.workspaceRoot, ...(cwd !== undefined ? { cwd } : {}) });
          const exited = child.exited.catch(() => null);
          const release = parent.effect(() => () => child.kill());
          let dialogInteraction = parent.interaction;
          const dialogOwner = parent.resources("sudo-password-retries");
          /** @type {Record<string, unknown> | undefined} */
          let result;
          let outputLength = 0;
          let failed = false;
          let finished = false;
          let canceled = false;
          let attempt = 1;
          /** @type {Promise<void> | undefined} */
          let pendingPrompt;
          const receive = lines(text => {
            try {
              const event = JSON.parse(text);
              if (event.type === "result" && result === undefined) { result = event.result; return; }
              if (event.type !== "password" || event.attempt !== attempt + 1 || result !== undefined) throw new Error("Invalid sudo event.");
              attempt = event.attempt;
              const nextAttempt = attempt;
              pendingPrompt = (pendingPrompt ?? Promise.resolve()).then(async () => {
                if (finished || canceled || signal.aborted || !parent.alive) return;
                const next = await dialogInteraction.input("Password not accepted. Try again (attempt " + nextAttempt + ").", "Sudo password (local only)", { signal: dialogOwner.signal, secret: true });
                if (finished) return;
                if (!next || signal.aborted || !parent.alive) canceled = true;
                else if (next.length > 4096 || /[\r\n\x00]/u.test(next)) throw new Error("Invalid password entry.");
                else passwords.push(next);
                await child.write(JSON.stringify({ password: canceled ? "" : next }) + "\n");
              }).catch(() => { failed = true; child.kill(); });
            } catch { failed = true; child.kill(); }
          }, () => { failed = true; child.kill(); });
          child.onStdout(text => {
            outputLength += text.length;
            if (outputLength > 400000) { failed = true; child.kill(); }
            else receive(text);
          });
          const timer = setInterval(() => {
            if (signal.aborted || !parent.alive) { canceled = true; child.kill(); }
          }, 50);
          // Only this private pipe carries the password; argv, env, logs, and tool output do not.
          try {
            await child.write(JSON.stringify({ argv, password, timeout_ms: timeoutMs }) + "\n");
            const exit = await exited;
            finished = true;
            await dialogOwner.dispose();
            await pendingPrompt;
            if (canceled || signal.aborted || !parent.alive) return { output: "Sudo request canceled. The command may have started.", is_error: true };
            if (failed || exit === null || exit.code !== 0) throw new Error("Sudo helper failed. The command may have started. No request data was logged.");
            if (!result || typeof result.stdout !== "string" || typeof result.stderr !== "string" ||
                (result.exit_code !== null && !Number.isInteger(result.exit_code)) ||
                (result.signal !== null && !Number.isInteger(result.signal)) || typeof result.timed_out !== "boolean" || typeof result.canceled !== "boolean") {
              throw new Error("Sudo helper returned an invalid result.");
            }
            let stdout = result.stdout, stderr = result.stderr;
            for (const secret of passwords) {
              stdout = stdout.replaceAll(secret, "[REDACTED]");
              stderr = stderr.replaceAll(secret, "[REDACTED]");
            }
            result.stdout = stdout;
            result.stderr = stderr;
            if (result.canceled) return { output: "Sudo password entry canceled. No command ran.", is_error: true };
            delete result.canceled;
            return { output: JSON.stringify(result), is_error: result.exit_code !== 0 || result.timed_out };
          } catch {
            if (signal.aborted || !parent.alive) return { output: "Sudo request canceled. The command may have started.", is_error: true };
            throw new Error("Sudo execution failed. The command may have started. No request data was logged.");
          } finally {
            finished = true;
            clearInterval(timer);
            release();
            await dialogOwner.dispose();
            await pendingPrompt;
          }
        } finally {
          password = "";
          passwords.length = 0;
          busy = false;
        }
      },
    };
    parent.tools.define(tool);
    {
const tuiBorrow = parent.get("tui");
const chatBorrow = parent.get("chat");
if (tuiBorrow && chatBorrow) {
const c = { ctx: parent, tui: tuiBorrow, chat: chatBorrow };

      /** @type {Map<Session, OwnedCommand>} */
      const active = new Map();
      /** @type {Promise<boolean> | null} */
      let supported = null;
      let serial = 0;
      c.chat.render({ sources: { user_shell: source => "!" + source.command.replace(/[\x00-\x20\x7f]+/gu, " ") + (source.timed_out ? " · timed out" : source.signal != null ? " · signal " + source.signal : source.exit_code != null ? " · exit " + source.exit_code : "") } });
      c.ctx.advise(Session.prototype, "send", "around", function (next, content, composer) {
        const first = content[0];
        if (!first || first.type !== "text" || first.text[0] !== "!") return next(content, composer);
        return submit(this, content, composer);
      });
      c.tui.keymap.add({ "ctrl+c": () => {
        const session = currentPane()?.session;
        const ownedCommand = session ? active.get(session) : undefined;
        if (!ownedCommand) return false;
        void ownedCommand.owner.dispose();
        return true;
      } }, "chat && !overlay");

      /** @param {Session} session @param {readonly Wire.ContentPart[]} content @param {Composer} composer */
      function submit(session, content, composer) {
        if (content.length !== 1) { c.ctx.interaction.notify("Remove attachments before a ! command.", "warn"); return false; }
        const part = /** @type {Extract<Wire.ContentPart, { type: "text" }>} */ (content[0]);
        const command = part.text.slice(1).trim();
        if (!command) { c.ctx.interaction.notify("Type a command after !.", "warn"); return false; }
        if (active.has(session) || session.creating) { c.ctx.interaction.notify("Wait for the current command or chat creation.", "warn"); return false; }
        const snapshot = composer.snapshot();
        const owner = parent.resources("composer-command-" + (++serial));
        const commandCtx = owner;
        const ownedCommand = { session, composer, command, context: commandCtx, owner, started: false };
        active.set(session, ownedCommand);
        run(ownedCommand).catch((error) => {
          if (!c.ctx.alive) return;
          if (!ownedCommand.started && composer.text === "") composer.restore(snapshot);
          c.ctx.interaction.notify(ownedCommand.started ? "Command output could not be saved. The command may have run. Check its effects before running it again." : "Could not start the command. No command ran. " + String(error), "error");
        }).finally(() => { active.delete(session); void owner.dispose(); });
        return true;
      }

      /** @param {OwnedCommand} ownedCommand */
      async function run(ownedCommand) {
        const { session, command, context: commandCtx } = ownedCommand;
        supported ??= client.request("initialize").then(result => result.protocol >= 2);
        if (!await supported) throw new Error("Restart Yuke with the build that supports ! commands.");
        if (commandCtx.signal.aborted) return;
        const id = session.sessionId || await session.startChat(null, ownedCommand.composer);
        const workspace = (await client.sessionGet(id)).session.root;
        if (commandCtx.signal.aborted || !parent.alive) return;
        /** @type {{ command: string, exit_code?: number, signal?: number, timed_out: boolean }} */
        const status = { command, exit_code: undefined, signal: undefined, timed_out: false };
        let output = "";
        const sudo = /^(?:sudo|\/usr\/bin\/sudo)(?:\s+|$)/u.exec(command);
        if (sudo) {
          const config = env.get("XDG_CONFIG_HOME") || (env.get("HOME") + "/.config");
          const helper = config + "/" + (env.get("YUKE_APPNAME") || "yuke") + "/plugins/sudo-command.py";
          const resolved = await exec("python3 " + quote(helper) + " --resolve " + quote(command.slice(sudo[0].length)), { workspaceRoot: workspace, signal: commandCtx.signal, maxBytes: 65536 });
          if (resolved.code !== 0 || resolved.stdoutDropped > 0) throw new Error(resolved.stderr?.trim() || "Could not resolve the sudo command.");
          const argv = JSON.parse(resolved.stdout);
          try {
            ownedCommand.started = true;
            const result = await tool.execute({ argv, reason: "Run the !sudo command you entered in the composer.", timeout_ms: 600000 }, commandCtx.signal, { workspaceRoot: workspace });
            try {
              const value = JSON.parse(result.output);
              status.exit_code = value.exit_code ?? undefined;
              status.signal = value.signal ?? undefined;
              status.timed_out = value.timed_out;
              output = value.stdout + (value.stderr ? (value.stdout && !value.stdout.endsWith("\n") ? "\n" : "") + value.stderr : "");
            } catch { output = result.output; }
          } catch { output = commandCtx.signal.aborted ? "Sudo command canceled. It may have started." : "Sudo command failed. It may have started."; }
        } else {
          c.ctx.interaction.notify("Running !" + command.replace(/\s+/gu, " ") + " · Ctrl+C stops it.");
          try {
            ownedCommand.started = true;
            const result = await exec(command, { workspaceRoot: workspace, signal: commandCtx.signal, timeoutMs: 600000, maxBytes: 49152, mergeStderr: true, log: false });
            status.exit_code = result.code ?? undefined;
            status.signal = result.signal ?? undefined;
            status.timed_out = result.timedOut;
            output = result.stdout;
          } catch {
            output = commandCtx.signal.aborted ? "Command canceled. It may have started." : "Command execution failed. It may have started.";
          }
        }
        if (!parent.alive) return;
        if (!output) output = "[no output]";
        if (status.timed_out) output += "\n[Timed out after 600000 ms.]";
        try { await client.request("session.record_command", { session_id: id, command: status, output }); }
        catch {
          if (!parent.alive) return;
          openDetails("!" + command, [{ label: "Command output (not saved to the chat)", text: output }]);
          c.ctx.interaction.notify("The command finished, but Yuke could not save its output. Do not run it again to fix this save failure.", "error");
        }
      }
}
}
  
}
