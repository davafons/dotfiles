#!/usr/bin/env python3
"""Read jj workspace snapshots and optional live tracked files without mutating history."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys


def run(argv, cwd):
    result = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip())
    return result.stdout


def jj(root, operation, *args):
    return run(["jj", "--ignore-working-copy", "--at-operation=" + operation,
                "--no-pager", "--color=never", *args], root)


def live_files(root, operation, commit, workspace):
    template = 'json(path) ++ "\\t" ++ json(file_type) ++ "\\t" ++ json(executable) ++ "\\n"'
    rows = jj(root, operation, "file", "list", "-r", commit, "-T", template).decode().splitlines()
    changed, unknown = [], []
    for row in rows:
        name, kind, executable = map(json.loads, row.split("\t"))
        path = workspace / name
        if kind not in ("file", "symlink"):
            unknown.append({"path": name, "reason": kind})
            continue
        try:
            before = path.lstat()
            if kind == "symlink":
                actual = os.fsencode(os.readlink(path))
            elif path.is_symlink() or not path.is_file():
                changed.append(name)
                continue
            else:
                actual = path.read_bytes()
            expected = jj(root, operation, "file", "show", "-r", commit, "--", name)
            after = path.lstat()
            if (before.st_mtime_ns, before.st_ctime_ns, before.st_ino, before.st_size) != (after.st_mtime_ns, after.st_ctime_ns, after.st_ino, after.st_size):
                unknown.append({"path": name, "reason": "changed during read"})
            elif actual != expected or (kind == "file" and bool(after.st_mode & 0o111) != executable):
                changed.append(name)
        except FileNotFoundError:
            changed.append(name)
        except (OSError, RuntimeError) as error:
            unknown.append({"path": name, "reason": str(error)})
    return {"checked_files": len(rows), "changed": changed, "unknown": unknown,
            "untracked_and_ignored": "not audited"}


def audit(path, base, active, check_live):
    root = path.resolve(strict=True)
    for candidate in (root, *root.parents):
        if (candidate / ".jj").is_dir():
            root = candidate
            break
        if (candidate / ".git").exists():
            raise RuntimeError("Not a jj workspace. This audit never falls back to Git.")
    else:
        raise RuntimeError("Not a jj workspace.")
    operation = jj(root, "@", "op", "log", "--no-graph", "--limit", "1", "-T", "id").decode()
    base_id = jj(root, operation, "log", "--no-graph", "-r", base, "-T", "commit_id").decode()
    if len(base_id) != 40:
        raise RuntimeError("The base must resolve to exactly one commit.")
    template = 'json(name) ++ "\\t" ++ json(root) ++ "\\t" ++ json(target) ++ "\\n"'
    result = {"operation": operation, "base": base, "base_commit": base_id, "workspaces": []}
    for line in jj(root, operation, "workspace", "list", "-T", template).decode().splitlines():
        name, location, commit = map(json.loads, line.split("\t"))
        workspace = Path(location)
        revision = commit["commit_id"]
        status = jj(root, operation, "log", "--no-graph", "-r", revision, "-T",
                    'json(diff.files().len()) ++ "\\t" ++ json(conflict)').decode().split("\t")
        ancestor = jj(root, operation, "log", "--no-graph", "-r", revision + " & ::" + base_id, "-T", "commit_id").decode()
        refs = jj(root, operation, "bookmark", "list", "--all-remotes", "-r", revision, "-T", 'json(self) ++ "\\n"').decode()
        size = subprocess.run(["du", "-sk", str(workspace)], capture_output=True, text=True, timeout=60)
        age = datetime.now(timezone.utc) - datetime.fromisoformat(commit["committer"]["timestamp"])
        row = {"name": name, "path": location, "commit": revision,
               "captured_changed_files": json.loads(status[0]), "conflict": json.loads(status[1]),
               "captured_commit_age_days": max(0, age.days), "ancestor_of_base": bool(ancestor),
               "size_kib": int(size.stdout.split()[0]) if size.returncode == 0 else None,
               "bookmark_refs": [json.loads(item) for item in refs.splitlines()],
               "pr_state": "not queried", "latest_chat": "not queried", "usage": "unknown",
               "live_files": live_files(root, operation, revision, workspace) if check_live else "not checked"}
        if workspace == root or (workspace / ".jj/repo").is_dir():
            row["bucket"] = "hold-primary-or-current"
        elif name in active or location in active:
            row["usage"] = "active or pinned per supplied set"
            row["bucket"] = "hold-in-use"
        elif row["conflict"] or row["captured_changed_files"] or (isinstance(row["live_files"], dict) and row["live_files"]["changed"]):
            row["bucket"] = "hold-work"
        else:
            row["bucket"] = "verify-usage-and-disk"
        result["workspaces"].append(row)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("-b", "--base", default="main")
    parser.add_argument("--active", action="append", default=[], help="Known active/pinned workspace name or exact path; repeatable")
    parser.add_argument("--check-live-files", action="store_true", help="Compare tracked bytes and modes without snapshotting; ignored/untracked files remain unaudited")
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.repo, args.base, args.active, args.check_live_files), indent=2))
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
