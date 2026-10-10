#!/usr/bin/env python3
"""jj-aware Herdr checkouts, transient pickers, and read-only sidebar metadata."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import socket
import subprocess
import sys

PLUGIN = "david.workspaces"
SOURCE = "plugin:" + PLUGIN
TOKENS = ("checkout", "revision", "change_description", "vcs_status")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def clean(value, limit=80):
    """Keep terminal controls and multiline descriptions out of sidebar tokens."""
    return " ".join("".join(c for c in str(value) if c.isprintable() or c.isspace()).split())[:limit]


def run(argv, cwd=None):
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeError(clean(result.stderr or result.stdout, 500) or f"{argv[0]} failed")
    return result.stdout.strip()


def request(method, params=None):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(10)
        connection.connect(os.environ["HERDR_SOCKET_PATH"])
        connection.sendall((json.dumps({"id": PLUGIN, "method": method, "params": params or {}}) + "\n").encode())
        with connection.makefile("rb") as replies:
            reply = json.loads(replies.readline())
    if "error" in reply:
        raise RuntimeError(str(reply["error"]))
    return reply["result"]


def repository(cwd):
    """Respect nested repositories; prefer jj over Git in colocated checkouts."""
    if not cwd:
        return None
    path = Path(cwd).expanduser().resolve()
    if not path.is_dir():
        return None
    for root in (path, *path.parents):
        if (root / ".jj").exists():
            return "jj", root
        if (root / ".git").exists():
            return "git", root
    return None


def jj(root, *args):
    # Display must never snapshot, rebase, or merge concurrent operations.
    return run(["jj", "--ignore-working-copy", "--at-operation=@", "--color=never", "--no-pager", *args], root)


def jj_checkouts(root):
    names = jj(root, "workspace", "list", "-T", 'name ++ "\\n"').splitlines()
    checkouts = []
    for name in names:
        path = Path(jj(root, "workspace", "root", "--name", name)).resolve()
        checkouts.append({"name": name, "path": str(path)})
    return checkouts


def status(cwd):
    repo = repository(cwd)
    if not repo:
        return {key: None for key in TOKENS}
    kind, root = repo
    if kind == "jj":
        checkouts = jj_checkouts(root)
        name = next((item["name"] for item in checkouts if Path(item["path"]) == root), root.name)
        template = ('json(change_id.short(8)) ++ "\\n" ++ json(description.first_line()) ++ "\\n" '
                    '++ json(conflict) ++ "\\n" ++ json(bookmarks.map(|b| b.name())) '
                    '++ "\\n" ++ json(diff.files().len())')
        change, description, conflict, bookmarks, count = [json.loads(line) for line in jj(root, "log", "-r", "@", "--no-graph", "-T", template).splitlines()]
        # Count the saved @ tree without rendering potentially enormous patches.
        state = f"{count} file{'s' if count != 1 else ''}" if count else "empty"
        if conflict:
            state += " · CONFLICT"
        if bookmarks:
            state += " · " + ", ".join(bookmarks)
        return {"checkout": clean(name), "revision": clean(change),
                "change_description": clean(description or "(no description)"), "vcs_status": clean(state)}

    # Never enter this path for a jj checkout, including linked jj workspaces.
    def git(*args):
        return run(["git", "--no-optional-locks", "-C", str(root), *args])
    rows = git("status", "--porcelain=v1", "-z").split("\0")
    count = 0
    conflict = False
    index = 0
    while index < len(rows):
        row = rows[index]
        if row:
            count += 1
            code = row[:2]
            conflict |= code in {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
            if "R" in code or "C" in code:
                index += 1  # Rename/copy source path is another NUL-delimited field.
        index += 1
    head = git("rev-parse", "--verify", "--quiet", "HEAD") if git_has_head(root) else ""
    branch = git("symbolic-ref", "--short", "HEAD") if not head else ""
    if head:
        branch = git("branch", "--show-current") or f"detached {head[:8]}"
    state = f"{count} file{'s' if count != 1 else ''}" if count else "clean"
    if conflict:
        state += " · CONFLICT"
    return {"checkout": clean(root.name), "revision": clean(branch),
            "change_description": None, "vcs_status": state}


def git_has_head(root):
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(root), "rev-parse", "--verify", "--quiet", "HEAD"], capture_output=True, timeout=15)
    return result.returncode == 0


def active_pane(snapshot, workspace):
    """Use the active tab's selected pane even when this workspace is unfocused."""
    for layout in snapshot["layouts"]:
        if layout["tab_id"] == workspace["active_tab_id"]:
            pane_id = layout.get("focused_pane_id")
            return next((pane for pane in snapshot["panes"] if pane["pane_id"] == pane_id), None)
    return next((pane for pane in snapshot["panes"] if pane["tab_id"] == workspace["active_tab_id"]), None)


def pane_cwd(pane):
    if not pane:
        return None
    return pane.get("foreground_cwd") or pane.get("cwd")


def project_root(root):
    """Linked jj workspaces store the original .jj/repo path in a file."""
    store = root / ".jj" / "repo"
    if store.is_file():
        target = Path(store.read_text().strip())
        if not target.is_absolute():
            target = store.parent / target
        return target.resolve().parent.parent
    return root


def project_name(root):
    return project_root(root).name


def sync():
    state = Path(os.environ["HERDR_PLUGIN_STATE_DIR"])
    state.mkdir(parents=True, exist_ok=True)
    session = hashlib.sha256(os.environ["HERDR_SOCKET_PATH"].encode()).hexdigest()[:12]
    with (state / f"sync-{session}.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return  # A refresh is already in flight; never queue event storms.
        snapshot = request("session.snapshot")["snapshot"]
        cache = {}

        def metadata(cwd):
            repo = repository(cwd)
            key = str(repo[1]) if repo else None
            if key not in cache:
                try:
                    cache[key] = status(cwd)
                except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                    print(f"status {cwd}: {error}", file=sys.stderr)
                    cache[key] = {key: None for key in TOKENS}
                    cache[key]["vcs_status"] = "status unavailable" if repo else None
            return cache[key]

        # Publish heartbeats: expiring tokens disappear if the refresher stops.
        for workspace in snapshot["workspaces"]:
            tokens = metadata(pane_cwd(active_pane(snapshot, workspace)))
            request("workspace.report_metadata", {"workspace_id": workspace["workspace_id"],
                    "source": SOURCE, "tokens": tokens, "ttl_ms": 60000 if sys.platform == "darwin" else None})
        for pane in snapshot["panes"]:
            request("pane.report_metadata", {"pane_id": pane["pane_id"], "source": SOURCE,
                    "tokens": metadata(pane_cwd(pane)), "ttl_ms": 60000 if sys.platform == "darwin" else None})


def context():
    return json.loads(os.environ.get("HERDR_PLUGIN_CONTEXT_JSON", "{}"))


def origin():
    ctx = context()
    cwd = ctx.get("focused_pane_cwd") or ctx.get("workspace_cwd")
    if not cwd and os.environ.get("HERDR_PANE_ID"):
        pane = request("pane.get", {"pane_id": os.environ["HERDR_PANE_ID"]})["pane"]
        cwd = pane_cwd(pane)
    return cwd or os.getcwd()


def open_popup(mode):
    cwd = origin()
    # Popup entrypoints are session-modal; Herdr rejects explicit pane/workspace targets.
    # Keep the process cwd at the plugin root so Python can find workspaces.py.
    request("plugin.pane.open", {"plugin_id": PLUGIN, "entrypoint": mode,
            "env": {"HERDR_CHECKOUT_ORIGIN": cwd}, "focus": True})


def open_jj(path, name, focus=True):
    root = Path(path).expanduser().resolve()
    if repository(root) != ("jj", root):
        raise RuntimeError(f"Not a jj workspace root: {root}")
    # Reuse an existing Herdr workspace rather than opening duplicates.
    snapshot = request("session.snapshot")["snapshot"]
    for workspace in snapshot["workspaces"]:
        panes = [pane for pane in snapshot["panes"] if pane["workspace_id"] == workspace["workspace_id"]]
        selected = active_pane(snapshot, workspace)
        panes.sort(key=lambda pane: pane != selected)
        for pane in panes:
            if repository(pane_cwd(pane)) == ("jj", root):
                if focus:
                    request("pane.focus", {"pane_id": pane["pane_id"]})
                return workspace
    return request("workspace.create", {"cwd": str(root), "label": f"{project_name(root)} / {name}", "focus": focus})["workspace"]


def create_jj(root, name, destination, focus=True):
    if not NAME.fullmatch(name) or name in {".", ".."}:
        raise RuntimeError("Use a name starting with a letter/digit, containing only letters, digits, ., _, or -")
    if name in {item["name"] for item in jj_checkouts(root)}:
        raise RuntimeError(f"jj workspace already exists: {name}")
    path = Path(destination).expanduser().resolve()
    if path.exists():
        raise RuntimeError(f"Destination already exists: {path}")
    # Validate main before creating a directory; do not guess another base.
    jj(root, "log", "-r", "main", "--no-graph", "-T", 'commit_id ++ "\\n"')
    path.parent.mkdir(parents=True, exist_ok=True)
    run(["jj", "--color=never", "--no-pager", "--config", 'signing.behavior="drop"',
         "workspace", "add", "--name", name, "-r", "main", str(path)], root)
    try:
        return open_jj(path, name, focus)
    except Exception as error:
        raise RuntimeError(f"Created jj workspace at {path}, but Herdr could not open it. Use open-existing to retry. {error}") from error


def default_destination(root, name):
    project = project_root(root)
    digest = hashlib.sha256(str(project).encode()).hexdigest()[:8]
    return Path.home() / ".herdr" / "jj-workspaces" / f"{project.name}-{digest}" / name


def choose(items, heading):
    if not shutil.which("fzf"):
        raise RuntimeError("Install fzf to use the checkout picker")
    lines = [f"{index}\t{clean(label, 300)}" for index, label in enumerate(items)]
    result = subprocess.run(["fzf", "--delimiter=\t", "--with-nth=2..", "--no-multi", "--layout=reverse", "--header", heading],
                            input="\n".join(lines), text=True, stdout=subprocess.PIPE)
    if result.returncode in (1, 130):
        return None
    if result.returncode:
        raise RuntimeError("fzf failed")
    return int(result.stdout.split("\t", 1)[0])


def ui(mode):
    cwd = os.environ.get("HERDR_CHECKOUT_ORIGIN") or origin()
    repo = repository(cwd)
    if not repo:
        raise RuntimeError(f"No jj or Git repository at {cwd}")
    kind, root = repo
    if mode == "create":
        print(f"Create {kind} checkout from main\nRepository: {root}\nCtrl-C cancels.\n")
        name = input("Workspace/branch name: ").strip()
        if not name:
            return
        if kind == "jj":
            destination = input(f"Checkout path [{default_destination(root, name)}]: ").strip()
            create_jj(root, name, destination or default_destination(root, name))
        else:
            request("worktree.create", {"cwd": str(root), "branch": name, "base": "main", "focus": True})
    else:
        if kind == "jj":
            items = jj_checkouts(root)
            labels = [f"{'* ' if Path(item['path']) == root else '  '}{item['name']}  {item['path']}" for item in items]
            selected = choose(labels, "jj workspaces · * current checkout · Enter opens · Esc cancels")
            if selected is not None:
                item = items[selected]
                open_jj(item["path"], item["name"])
        else:
            items = request("worktree.list", {"cwd": str(root)})["worktrees"]
            items = [item for item in items if not item["is_bare"] and not item["is_prunable"]]
            labels = [f"{'* ' if Path(item['path']).resolve() == root else '  '}{item.get('branch') or 'detached'}  {item['path']}" for item in items]
            selected = choose(labels, "Git worktrees · * current checkout · Enter opens · Esc cancels")
            if selected is not None:
                request("worktree.open", {"cwd": str(root), "path": items[selected]["path"], "focus": True})
    # Exiting closes the popup naturally; popup.close would kill this process.
    sync()


def install_refresh():
    """Use launchd for periodic one-shot refreshes, not unsupervised startup daemons."""
    if sys.platform != "darwin":
        return
    sock = os.environ["HERDR_SOCKET_PATH"]
    digest = hashlib.sha256(sock.encode()).hexdigest()[:12]
    label = f"dev.herdr.workspaces.{digest}"
    directory = Path.home() / "Library" / "LaunchAgents"
    directory.mkdir(parents=True, exist_ok=True)
    state = Path(os.environ["HERDR_PLUGIN_STATE_DIR"])
    state.mkdir(parents=True, exist_ok=True)
    plist = directory / f"{label}.plist"
    config = {"Label": label, "ProgramArguments": [sys.executable, str(Path(__file__).resolve()), "sync"],
              "RunAtLoad": True, "StartInterval": 15,
              "EnvironmentVariables": {"HERDR_ENV": "1", "HERDR_SOCKET_PATH": sock,
                                       "HERDR_PLUGIN_STATE_DIR": str(state), "PATH": os.environ["PATH"]},
              "StandardErrorPath": str(state / f"refresh-{digest}.log")}
    contents = plistlib.dumps(config)
    # No bootout/restart during normal server startup if already configured.
    if plist.exists() and plist.read_bytes() == contents:
        result = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{label}"], capture_output=True)
        if result.returncode == 0:
            return
    else:
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{label}"], capture_output=True)
        plist.write_bytes(contents)
    run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)])
    print(f"Installed 15-second read-only refresh: {label}")


def uninstall_refresh():
    digest = hashlib.sha256(os.environ["HERDR_SOCKET_PATH"].encode()).hexdigest()[:12]
    label = f"dev.herdr.workspaces.{digest}"
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{label}"], capture_output=True)
    (Path.home() / "Library" / "LaunchAgents" / f"{label}.plist").unlink(missing_ok=True)
    print(f"Removed automatic refresh: {label}")


def periodic_refresh_enabled():
    # A launchd job outlives its Herdr plugin; don't publish after disable/unlink.
    plugins = request("plugin.list")["plugins"]
    return any(plugin["plugin_id"] == PLUGIN and plugin["enabled"] for plugin in plugins)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["sync", "create", "open", "ui-create", "ui-open", "install-refresh", "uninstall-refresh", "create-jj", "open-jj"])
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--name")
    parser.add_argument("--path")
    parser.add_argument("--no-focus", action="store_true")
    args = parser.parse_args()
    if os.environ.get("HERDR_ENV") != "1":
        parser.error("Run inside Herdr")
    if args.command == "sync":
        # launchd runs even while Herdr is stopped; do not autostart a server.
        if Path(os.environ["HERDR_SOCKET_PATH"]).exists():
            if os.environ.get("HERDR_PLUGIN_ID") or periodic_refresh_enabled():
                sync()
    elif args.command == "install-refresh":
        install_refresh()
    elif args.command == "uninstall-refresh":
        uninstall_refresh()
    elif args.command in {"create", "open"}:
        open_popup(args.command)
    elif args.command.startswith("ui-"):
        try:
            ui(args.command[3:])
        except (EOFError, KeyboardInterrupt):
            return
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
            print(f"\n{error}")
            input("\nPress Enter to close…")
    elif args.command == "create-jj":
        repo = repository(args.cwd)
        if not repo or repo[0] != "jj" or not args.name:
            parser.error("create-jj needs a jj --cwd and --name")
        create_jj(repo[1], args.name, args.path or default_destination(repo[1], args.name), not args.no_focus)
        sync()
    elif args.command == "open-jj":
        if not args.path:
            parser.error("open-jj needs --path")
        root = Path(args.path).expanduser().resolve()
        items = jj_checkouts(root)
        name = next(item["name"] for item in items if Path(item["path"]) == root)
        open_jj(root, name, not args.no_focus)
        sync()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
