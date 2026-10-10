# Sudo commands

The profile adds the `sudo_command` model tool. Load the profile with `/reload`. A restart also loads it.

Ask the agent to run a command that needs root. The agent supplies an absolute executable path, separate arguments, and a reason. For example:

```json
{
  "argv": ["/usr/bin/id", "-u"],
  "reason": "Check that the command runs as root."
}
```

Yuke shows the reason, executable, arguments, workspace, directory, and deadline in a confirmation dialog. Review the whole command. Select **Run as root** only if you approve it. Press Escape to cancel.

After approval, Yuke opens a masked password dialog. Enter the password there, never in chat. If sudo rejects the password, Yuke opens another masked dialog with the attempt number. Sudo controls the attempt limit through `passwd_tries`, which defaults to three. These dialogs stay inside the same tool call. The model receives no intermediate authentication failure. Press Escape to cancel.

Each call requires one command approval. Password retries do not restart the command or request approval again. The plugin permits one active request at a time.

The tool returns stdout, stderr, exit code, signal, and timeout status. A failure also returns the command output. The helper keeps at most 24 KiB per stream. It saves no output log. The default deadline is 120 seconds. The maximum is 600 seconds. Cancellation and a deadline request termination; they cannot undo system changes or stop descendants that detach from the process group.

`cwd` selects a directory relative to the workspace or an absolute directory. `timeout_ms` sets the execution deadline. The command receives closed stdin. This tool does not support terminal editors, interactive installers, or further input prompts. It uses no shell expansion. An explicit shell executable can still run a script as root; review it with care.

## Direct composer commands

Type `!` at the start of a message to run a command without asking the agent to execute it:

```text
!pwd
!ls -la
!printf 'hello\n' | cat
!sudo id -u
```

Normal commands use the workspace's shell. They support pipes, redirects, and shell expansion. Each command starts a new shell. `!cd /tmp` does not change the workspace or the directory of the next command. Stdin is closed. The deadline is 600 seconds. Output keeps at most 48 KiB, with its head and tail. The plugin saves no output log. Ctrl+C stops the command in the focused chat. One direct command can run per chat.

The command and result appear in the transcript. Yuke saves them for the next model request without starting a model reply. If the agent is already running, a later required round can read the result. Command output alone does not extend that run. This matches [Codex's result-sharing behavior](https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/core/src/tasks/user_shell.rs). Output can contain secrets other than the sudo password. Direct commands share that output with the model when the next request runs.

`!sudo` and `!/usr/bin/sudo` use the same approval and masked-password flow as `sudo_command`. The helper resolves the executable through PATH before approval. Quotes keep arguments together. Sudo options, shell operators, and shell expansion are not supported after the sudo prefix. For a root script, name the shell explicitly, for example `!sudo /bin/sh -c 'id -u | cat'`. Review every argument in the approval dialog. The entire script in that example runs as root.

A declined approval or canceled password dialog runs no privileged command. A command failure does not cause another attempt. Password retries stay inside one sudo process. Sudo output has the same 24 KiB per-stream limits as the tool.

The prefix preserves normal messages and slash commands. Remove attachments before a direct command. A second command stays in the composer while the first runs. Navigation does not move a command's output into another chat. A save failure shows the output in a local details window and does not restore the command for another execution.

The prefix needs the Yuke build with protocol version 2 and `session.record_command`. Restart Yuke after installing that build. `/reload` alone cannot add native APIs to an old process. Select a model first if the profile has no saved default.

## Password handling

The password is not a tool argument. The plugin sends it to a local Python helper through a private stdin pipe. The helper uses sudo's `askpass` mechanism. A private Unix socket transfers each password entry to the askpass process. The socket directory has mode `0700`. The socket has mode `0600`. The temporary askpass script contains paths, not the password.

The helper runs `/usr/bin/sudo -k -A -- <executable> <arguments>`. With a command, `-k` ignores cached credentials and does not update them. The askpass process supplies the password to sudo, not to the command. If policy permits the command without authentication, the command still receives closed stdin. Each new askpass request opens a new password dialog. The helper does not resubmit a rejected password. The tool returns to the model after the command finishes, sudo exhausts its attempts or reports another failure, you cancel, or the deadline expires. A command failure does not cause another execution attempt.

The helper redacts every entered password from stdout and stderr before it buffers output. It removes its temporary files when it exits normally or handles cancellation. It disables its own core dumps. The plugin does not send the password to the model or save it in arguments, environment variables, files, or logs.

This is not an isolation boundary against other installed plugins or processes under your user account. The TUI, plugin, helper, and sudo hold the password in memory. JavaScript and Python cannot guarantee erasure of those bytes. A crash or forced kill can bypass normal cleanup. Command output can contain other secrets. The tool sends that output to the model without a second review dialog. System sudo policy can log command arguments and command output.

The tool requires the TUI and Python 3. Headless calls fail without running a command. It does not change sudoers or enable passwordless sudo.

## Verification

Run these checks from the dotfiles repository:

```sh
python3 yuke/.config/yuke/tests/check-sudo-command.py
node yuke/.config/yuke/tests/check-sudo-command.mjs
python3 yuke/.config/yuke/tests/check-sudo-command-tui.py
node yuke/.config/yuke/tests/check-composer-command.mjs
python3 yuke/.config/yuke/tests/check-composer-command-tui.py
tsc -p ~/.config/yuke/jsconfig.json
yuke check
```

The tests use dummy passwords and fake sudo processes. The TUI tests use isolated profiles and stores in detached tmux. The composer test uses a local fake model provider to check saved context and prove that direct commands make no model requests. Both TUI scripts accept `--binary /path/to/yuke`. No test requests root access. A live sudo command requires your approval and password entry.
