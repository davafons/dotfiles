#!/usr/bin/env python3
"""Private project work records. SQLite serializes writers across Yuke processes."""
import contextlib
import json
import os
import re
from pathlib import Path
import sqlite3
import sys
import time
import uuid

STATUSES = ("now", "later", "blocked", "review", "done")


def text(value, name, limit, empty=False):
    if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
        raise ValueError(f"{name} must be {'optional' if empty else 'nonempty'} text of at most {limit} characters")
    if any((ord(c) < 32 and c not in "\n\t") or 127 <= ord(c) <= 159 for c in value):
        raise ValueError(f"{name} must not contain terminal control codes")
    if name in ("root", "session", "site", "id", "task_id", "title") and any(c in value for c in "\n\t"):
        raise ValueError(f"{name} must be one line")
    return value.strip()


def project(root):
    """Group linked jj/Git checkouts without invoking or changing version control."""
    path = Path(text(root, "root", 4096)).resolve(strict=True)
    if not path.is_dir():
        raise ValueError("root must be a directory")
    for checkout in (path, *path.parents):
        if (checkout / ".jj").exists():
            repo = checkout / ".jj" / "repo"
            if repo.is_file():
                target = Path(repo.read_text().strip())
                repo = target if target.is_absolute() else repo.parent / target
            repo = repo.resolve(strict=True)
            return "jj:" + str(repo), repo.parent.parent.name, str(checkout)
        git = checkout / ".git"
        if git.exists():
            if git.is_file():
                value = git.read_text().strip()
                if not value.startswith("gitdir: "):
                    raise ValueError("invalid Git checkout pointer")
                target = Path(value[8:])
                git = target if target.is_absolute() else checkout / target
            common = git / "commondir"
            if common.is_file():
                target = Path(common.read_text().strip())
                git = target if target.is_absolute() else git / target
            git = git.resolve(strict=True)
            return "git:" + str(git), git.parent.name, str(checkout)
    return "path:" + str(path), path.name, str(path)


def operate(database, args):
    if not isinstance(args, dict):
        raise ValueError("work arguments must be an object")
    action = args.get("action")
    fields = {
        "list": ("offset", "include_done"), "board": ("offsets", "include_done", "query"), "get": ("id",),
        "task": ("id", "version", "title", "status", "notes", "github_url"),
        "linked": ("github_url",),
        "checkpoint": ("task_id", "summary", "next_step", "verification"),
        "context": ("version", "goal", "notes"),
        "activity": ("observed_at",),
    }
    if action not in fields:
        raise ValueError("unknown work action")
    if set(args) - {"action", "root", "session", "site", *fields[action]}:
        raise ValueError("unknown work field")
    key, name, checkout = project(args.get("root"))
    session = text(args.get("session", ""), "session", 200, empty=True)
    site = text(args.get("site", ""), "site", 300, empty=True)
    now = int(time.time() * 1000)
    os.umask(0o077)
    path = Path(database)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("work database must not be a symlink")
    with contextlib.closing(sqlite3.connect(path, timeout=10)) as db, db:
        db.row_factory = sqlite3.Row
        db.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, goal TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
                version INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, project TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL,
                notes TEXT NOT NULL, session TEXT NOT NULL, root TEXT NOT NULL, site TEXT UNIQUE,
                updated INTEGER NOT NULL, version INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS tasks_project_status ON tasks(project, status, updated DESC, id);
            CREATE TABLE IF NOT EXISTS checkpoints (
                project TEXT NOT NULL, session TEXT NOT NULL, task_id TEXT NOT NULL,
                summary TEXT NOT NULL, next_step TEXT NOT NULL, verification TEXT NOT NULL,
                root TEXT NOT NULL, updated INTEGER NOT NULL, PRIMARY KEY(project, session));
            CREATE TABLE IF NOT EXISTS activity (
                project TEXT NOT NULL, session TEXT NOT NULL, started INTEGER NOT NULL,
                PRIMARY KEY(project, session));
        """)
        db.execute("BEGIN IMMEDIATE")
        if "github_url" not in {row[1] for row in db.execute("PRAGMA table_info(tasks)")}:
            db.execute("ALTER TABLE tasks ADD COLUMN github_url TEXT NOT NULL DEFAULT ''")
        db.execute("INSERT OR IGNORE INTO projects(id) VALUES (?)", (key,))
        if action in ("list", "board"):
            context = dict(db.execute("SELECT goal, notes, version FROM projects WHERE id=?", (key,)).fetchone())
            include_done = args.get("include_done", False)
            if type(include_done) is not bool:
                raise ValueError("include_done must be boolean")
            if action == "list":
                offset = args.get("offset", 0)
                if type(offset) is not int or offset < 0:
                    raise ValueError("offset must be a nonnegative integer")
                count = db.execute("SELECT COUNT(*) FROM tasks WHERE project=? AND (? OR status!='done')",
                                   (key, include_done)).fetchone()[0]
                tasks = [dict(row) for row in db.execute(
                    "SELECT id, title, status, notes, session, root, updated, version, github_url FROM tasks WHERE project=? AND (? OR status!='done') ORDER BY updated DESC, id LIMIT 10 OFFSET ?",
                    (key, include_done, offset))]
                paging = {"total": count, "offset": offset}
            else:
                offsets = args.get("offsets", [0] * len(STATUSES))
                if not isinstance(offsets, list) or len(offsets) != len(STATUSES) or any(type(v) is not int or v < 0 for v in offsets):
                    raise ValueError("board offsets must be five nonnegative integers")
                query = text(args.get("query", ""), "query", 200, empty=True)
                counts = []
                tasks = []
                for index, status in enumerate(STATUSES):
                    count = db.execute("SELECT COUNT(*) FROM tasks WHERE project=? AND status=? AND instr(lower(title || ' ' || notes), lower(?))>0",
                                       (key, status, query)).fetchone()[0]
                    counts.append(count)
                    if status == "done" and not include_done:
                        continue
                    tasks.extend(dict(row) for row in db.execute(
                        "SELECT id, title, status, notes, session, root, updated, version, github_url FROM tasks WHERE project=? AND status=? AND instr(lower(title || ' ' || notes), lower(?))>0 ORDER BY updated DESC, id LIMIT 5 OFFSET ?",
                        (key, status, query, offsets[index])))
                paging = {"counts": counts, "offsets": offsets, "query": query, "include_done": include_done}
            checkpoints = [dict(row) for row in db.execute("""
                SELECT c.*, COALESCE(a.started, 0) > c.updated AS stale FROM checkpoints c
                LEFT JOIN activity a ON a.project=c.project AND a.session=c.session
                WHERE c.project=? ORDER BY c.updated DESC, c.session LIMIT 5""", (key,))]
            return {"project": key, "name": name, "root": checkout, "context": context,
                    "tasks": tasks, "checkpoints": checkpoints, **paging}
        if action == "linked":
            url = text(args.get("github_url"), "github_url", 500)
            return {"total": db.execute("SELECT COUNT(*) FROM tasks WHERE project=? AND github_url=?", (key, url)).fetchone()[0],
                    "tasks": [dict(row) for row in db.execute(
                "SELECT id, title, status, version, github_url FROM tasks WHERE project=? AND github_url=? ORDER BY updated DESC, id LIMIT 50", (key, url))]}
        if action == "get":
            ident = text(args.get("id"), "id", 100)
            row = db.execute("SELECT * FROM tasks WHERE project=? AND id=?", (key, ident)).fetchone()
            if not row:
                raise ValueError("task does not belong to this project")
            checkpoint = db.execute("""SELECT c.*, COALESCE(a.started, 0) > c.updated AS stale
                FROM checkpoints c LEFT JOIN activity a ON a.project=c.project AND a.session=c.session
                WHERE c.project=? AND c.task_id=? ORDER BY c.updated DESC LIMIT 1""", (key, ident)).fetchone()
            return {"task": dict(row), "checkpoint": dict(checkpoint) if checkpoint else None}
        if action == "context":
            goal = text(args.get("goal"), "goal", 2000, empty=True)
            notes = text(args.get("notes"), "notes", 4000, empty=True)
            version = args.get("version")
            if type(version) is not int or version < 0:
                raise ValueError("read work first; context requires its version")
            if not db.execute("UPDATE projects SET goal=?, notes=?, version=version+1 WHERE id=? AND version=?",
                              (goal, notes, key, version)).rowcount:
                raise ValueError("project context changed; refresh before editing")
            return {"version": version + 1}
        if action == "activity":
            if not session:
                raise ValueError("activity requires a session")
            observed = args.get("observed_at")
            if type(observed) is not int or observed < 0 or observed > now + 60000:
                raise ValueError("invalid activity time")
            db.execute("""INSERT INTO activity VALUES (?, ?, ?) ON CONFLICT(project, session)
                       DO UPDATE SET started=MAX(started, excluded.started)""", (key, session, observed))
            return {"recorded": True}
        if action == "checkpoint":
            if not session:
                raise ValueError("start a saved session before recording a checkpoint")
            summary = text(args.get("summary"), "summary", 4000)
            next_step = text(args.get("next_step"), "next_step", 2000)
            verification = text(args.get("verification"), "verification", 2000)
            task_id = text(args.get("task_id", ""), "task_id", 100, empty=True)
            if task_id and not db.execute("SELECT 1 FROM tasks WHERE project=? AND id=?", (key, task_id)).fetchone():
                raise ValueError("task does not belong to this project")
            db.execute("""INSERT INTO checkpoints VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(project, session) DO UPDATE SET task_id=excluded.task_id,
                       summary=excluded.summary, next_step=excluded.next_step,
                       verification=excluded.verification, root=excluded.root, updated=excluded.updated""",
                       (key, session, task_id, summary, next_step, verification, checkout, now))
            return {"session": session, "updated": now}
        ident = args.get("id")
        title = text(args.get("title"), "title", 200)
        notes = text(args.get("notes"), "notes", 4000, empty=True)
        github_url = None
        if "github_url" in args:
            github_url = text(args["github_url"], "github_url", 500, empty=True)
            if github_url and not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(issues|pull)/[1-9][0-9]*", github_url):
                raise ValueError("github_url must be a github.com issue or pull request URL")
        status = args.get("status")
        if status not in STATUSES:
            raise ValueError("status must be now, later, blocked, review, or done")
        if "id" in args:
            ident = text(ident, "id", 100)
            version = args.get("version")
            if type(version) is not int or version < 1:
                raise ValueError("read work first; task updates require its version")
            if not db.execute("""UPDATE tasks SET title=?, status=?, notes=?, github_url=COALESCE(?, github_url), version=version+1,
                              updated=? WHERE project=? AND id=? AND version=?""",
                              (title, status, notes, github_url, now, key, ident, version)).rowcount:
                raise ValueError("task changed or belongs to another project; refresh before editing")
            return {"id": ident, "version": version + 1}
        if "version" in args:
            raise ValueError("a new task must not have a version")
        if site:
            existing = db.execute("SELECT id, version FROM tasks WHERE site=? AND project=?", (site, key)).fetchone()
            if existing:
                return dict(existing)
        ident = "w-" + uuid.uuid4().hex[:16]
        db.execute("INSERT INTO tasks (id, project, title, status, notes, session, root, site, updated, version, github_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                   (ident, key, title, status, notes, session, checkout, site or None, now, github_url or ""))
        return {"id": ident, "version": 1}


if __name__ == "__main__":
    try:
        print(json.dumps(operate(sys.argv[1], json.loads(sys.argv[2])), ensure_ascii=False))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
