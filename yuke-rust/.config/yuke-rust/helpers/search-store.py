#!/usr/bin/env python3
"""Keep a rebuildable search index of public Yuke history and query workspace files."""
import json
import os
from pathlib import Path
import re
import selectors
import sqlite3
import subprocess
import sys
import time

FILE_LIMIT = 20000


def clean(text):
    return re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)


def fuzzy(query, value):
    query, value = query.casefold(), value.casefold()
    if not query:
        return 0
    position = 0
    score = 0
    for char in query:
        found = value.find(char, position)
        if found < 0:
            return None
        score += found - position
        position = found + 1
    return score


class Store:
    def __init__(self, path):
        os.umask(0o077)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(path, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, root TEXT NOT NULL,
                signature TEXT NOT NULL, expected TEXT NOT NULL, updated INTEGER NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS passages USING fts5(
                session_id UNINDEXED, message_id UNINDEXED, part_id UNINDEXED,
                role UNINDEXED, body, tokenize='unicode61'
            );
            CREATE TEMP TABLE stage (
                session_id TEXT, message_id INTEGER, part_id INTEGER, role TEXT, body TEXT,
                PRIMARY KEY(session_id, message_id, part_id)
            );
        """)
        self.files = {}

    def manifest(self, items, partial=False):
        if not partial:
            self.files.clear()
        wanted = {item["id"]: item for item in items}
        existing = {row["id"]: row["signature"] for row in self.db.execute("SELECT id, signature FROM sessions")}
        dirty = []
        with self.db:
            for sid in (() if partial else existing.keys() - wanted.keys()):
                self.db.execute("DELETE FROM passages WHERE session_id = ?", (sid,))
                self.db.execute("DELETE FROM sessions WHERE id = ?", (sid,))
            for sid, item in wanted.items():
                signature = item["signature"]
                ready = existing.get(sid) == signature
                if not ready:
                    dirty.append(sid)
                    self.db.execute("DELETE FROM passages WHERE session_id = ?", (sid,))
                self.db.execute("""INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET title=excluded.title, root=excluded.root,
                    signature=excluded.signature, expected=excluded.expected, updated=excluded.updated""",
                    (sid, item["title"], item["root"], signature if ready else "", signature, item["updated"]))
        return {"dirty": dirty}

    def begin(self, sid):
        with self.db:
            self.db.execute("DELETE FROM stage WHERE session_id = ?", (sid,))
        return {}

    def part(self, item):
        with self.db:
            self.db.execute("""INSERT INTO stage VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id, message_id, part_id) DO UPDATE SET body=body || excluded.body""",
                (item["session_id"], item["message_id"], item["part_id"], item["role"], item["body"]))
        return {}

    def finish(self, sid, signature):
        with self.db:
            row = self.db.execute("SELECT expected FROM sessions WHERE id = ?", (sid,)).fetchone()
            if row is None or row["expected"] != signature:
                raise RuntimeError("Chat changed during indexing. Refresh to retry.")
            self.db.execute("DELETE FROM passages WHERE session_id = ?", (sid,))
            self.db.execute("INSERT INTO passages SELECT * FROM stage WHERE session_id = ?", (sid,))
            self.db.execute("UPDATE sessions SET signature = ? WHERE id = ?", (signature, sid))
            self.db.execute("DELETE FROM stage WHERE session_id = ?", (sid,))
        return {}

    def paths(self, root):
        if root in self.files:
            return self.files[root]
        paths, capped = rg_lines(["--files", "--null"], root, FILE_LIMIT, delimiter=b"\0")
        self.files[root] = (sorted(paths), capped)
        return self.files[root]

    def search(self, query, source, root):
        query = query.strip()
        results, notes = [], []
        params = (root,) if root else ()
        where = "WHERE root = ?" if root else ""
        if source in ("all", "chats"):
            rows = self.db.execute(f"SELECT * FROM sessions {where} ORDER BY updated DESC, id", params)
            ranked = []
            for row in rows:
                fields = (row["title"], row["root"] if query.startswith("/") else Path(row["root"]).name, row["id"])
                scores = [score for field in fields if (score := fuzzy(query, field)) is not None]
                if scores:
                    ranked.append((min(scores), -row["updated"], row["id"], row))
            ranked.sort(key=lambda entry: entry[:3])
            cap = 20
            for *_, row in ranked[:cap]:
                results.append(dict(kind="session", key="session:" + row["id"], session_id=row["id"],
                                    title=row["title"], detail=row["root"], line=0, path="", message_id=0, part_id=0))
            if len(ranked) > cap:
                notes.append("Session results capped")
        if query and source in ("all", "chats"):
            words = re.findall(r"\w+", query, re.UNICODE)
            if len(words) > 16:
                notes.append("Chat search allows at most 16 words")
            elif words:
                match = " AND ".join('"' + word + '"*' for word in words)
                cap = 30 if source == "all" else 60
                condition = "AND s.root = ?" if root else ""
                rows = self.db.execute(f"""SELECT p.rowid, p.session_id, p.message_id, p.part_id, p.role,
                    s.title, s.root, snippet(passages, 4, '[', ']', ' … ', 24) excerpt
                    FROM passages p JOIN sessions s ON s.id = p.session_id
                    WHERE passages MATCH ? {condition} ORDER BY bm25(passages), s.updated DESC LIMIT ?""",
                    (match, *params, cap + 1)).fetchall()
                for row in rows[:cap]:
                    results.append(dict(kind="chat", key=f"chat:{row['session_id']}:{row['message_id']}:{row['part_id']}",
                                        session_id=row["session_id"], title=row["title"], detail=clean(row["role"] + " · " + row["excerpt"]),
                                        message_id=row["message_id"], part_id=row["part_id"], path="", line=0))
                if len(rows) > cap:
                    notes.append("Chat results capped")
            else:
                notes.append("Chat search needs a word or number")
        if root and source in ("all", "files"):
            try:
                paths, capped = self.paths(root)
                ranked_paths = []
                for path in paths:
                    score = fuzzy(query, path)
                    if score is not None:
                        ranked_paths.append((score, len(path), path))
                ranked_paths.sort()
                cap = 20 if source == "all" else 40
                for _, _, path in ranked_paths[:cap]:
                    results.append(dict(kind="file", key="file:" + path, session_id="", title=clean(path),
                                        detail="file path", path=path, line=1, message_id=0, part_id=0))
                if capped or len(ranked_paths) > cap:
                    notes.append("File paths capped")
            except (OSError, RuntimeError) as error:
                notes.append(str(error))
        if root and len(query) >= 2 and source in ("all", "files"):
            try:
                cap = 30 if source == "all" else 40
                lines, capped = rg_lines(["--json", "--fixed-strings", "--smart-case", "--max-columns", "2000", "--", query, "."], root, cap, matches=True)
                for line in lines:
                    event = json.loads(line)["data"]
                    path = event["path"].get("text")
                    body = event["lines"].get("text")
                    if path is None or body is None:
                        continue
                    path = path.removeprefix("./")
                    number = event["line_number"]
                    results.append(dict(kind="text", key=f"text:{path}:{number}", session_id="", title=clean(path) + ":" + str(number),
                                        detail=clean(body.strip()), path=path, line=number, message_id=0, part_id=0))
                if capped:
                    notes.append("File content results capped")
            except (OSError, RuntimeError) as error:
                notes.append(str(error))
        if not root and source in ("all", "files"):
            notes.append("Files use workspace scope; press Tab")
        if query:
            matched_sessions = {item["session_id"] for item in results if item["kind"] == "chat"}
            results = [item for item in results if item["kind"] != "session" or item["session_id"] not in matched_sessions]
            order = {"chat": 0, "text": 1, "file": 2, "session": 3}
            results.sort(key=lambda item: order[item["kind"]])
        return {"items": results, "note": " · ".join(notes)}

    def preview(self, item, root, query=""):
        if item["kind"] == "chat":
            row = self.db.execute("SELECT role, body FROM passages WHERE session_id = ? AND message_id = ? AND part_id = ?",
                                  (item["session_id"], item["message_id"], item["part_id"])).fetchone()
            if row is None:
                raise RuntimeError("This passage changed. Refresh the search.")
            body = clean(row["body"])
            words = re.findall(r"\w+", query, re.UNICODE)
            if words and len(words) <= 16:
                match = " AND ".join('"' + word + '"*' for word in words)
                render = "snippet(passages, 4, char(1), char(2), ' … ', 64)" if len(body) > 4000 else "highlight(passages, 4, char(1), char(2))"
                passage = self.db.execute(f"""SELECT {render}
                    FROM passages WHERE session_id = ? AND message_id = ? AND part_id = ?
                    AND passages MATCH ?""", (item["session_id"], item["message_id"], item["part_id"], match)).fetchone()
                if passage:
                    excerpt = passage[0]
                    if len(excerpt) > 4000:
                        start = max(0, excerpt.find("\x01") - 1200)
                        excerpt = excerpt[start:start + 4000]
                    matches = list(dict.fromkeys(clean(word) for word in re.findall("\x01([^\x02]*)(?:\x02|$)", excerpt, re.DOTALL)))
                    return {"text": clean(excerpt), "matches": matches, "note": "Matching passage" if len(body) > 4000 else ""}
            return {"text": body[:4000], "matches": [], "note": "Matching passage" if len(body) > 4000 else ""}
        if item["kind"] == "session":
            rows = self.db.execute("SELECT role, body FROM passages WHERE session_id = ? ORDER BY CAST(message_id AS INTEGER) DESC, CAST(part_id AS INTEGER) DESC LIMIT 4", (item["session_id"],)).fetchall()
            return {"text": "\n\n".join(clean(row["role"] + "\n" + row["body"][:8000]) for row in reversed(rows)) or "No indexed chat text yet.", "note": "Recent saved text"}
        if not root:
            raise RuntimeError("Choose workspace scope to preview a file.")
        base = Path(root).resolve()
        path = (base / item["path"]).resolve()
        if not path.is_relative_to(base):
            raise RuntimeError("File preview cannot leave the workspace.")
        start = max(1, item["line"] - 10)
        end = start + 100
        rows = []
        size = 0
        with path.open("rb") as file:
            for number in range(1, end + 1):
                raw = file.readline(16385)
                if not raw:
                    break
                if b"\0" in raw:
                    return {"text": "Binary file. Insert the path to reference it.", "note": ""}
                if len(raw) > 16384:
                    raise RuntimeError("File preview stopped at a line above 16 KiB.")
                if number >= start:
                    marker = "> " if number == item["line"] else "  "
                    value = marker + str(number) + "  " + clean(raw.decode("utf-8", errors="replace").rstrip())
                    rows.append(value)
                    size += len(value)
                if size > 65536:
                    break
        return {"text": "\n".join(rows), "note": "File preview · at most 100 lines"}

    def dispatch(self, request):
        action = request["action"]
        if action == "manifest":
            return self.manifest(request["items"], request.get("partial", False))
        if action == "begin":
            return self.begin(request["session_id"])
        if action == "part":
            return self.part(request)
        if action == "finish":
            return self.finish(request["session_id"], request["signature"])
        if action == "search":
            return self.search(request["query"], request["source"], request["root"])
        if action == "preview":
            return self.preview(request["item"], request["root"], request.get("query", ""))
        raise ValueError("Unknown search action")


def rg_lines(args, root, limit, delimiter=b"\n", matches=False):
    process = subprocess.Popen(["rg", *args], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "out")
    selector.register(process.stderr, selectors.EVENT_READ, "err")
    pending, errors = b"", b""
    found = []
    deadline = time.monotonic() + 5
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("File search exceeded 5 seconds; narrow the query")
            for key, _ in selector.select(remaining):
                data = os.read(key.fileobj.fileno(), 65536)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                if key.data == "err":
                    errors = (errors + data)[-4096:]
                    continue
                pending += data
                while delimiter in pending:
                    raw, pending = pending.split(delimiter, 1)
                    if matches and json.loads(raw).get("type") != "match":
                        continue
                    found.append(raw.decode("utf-8", errors="replace"))
                    if len(found) > limit:
                        return found[:limit], True
                if len(pending) > 1048576:
                    raise RuntimeError("File search line exceeds 1 MiB")
        code = process.wait(timeout=max(0.01, deadline - time.monotonic()))
        if code not in (0, 1) or errors:
            raise RuntimeError("File search: " + clean(errors.decode(errors="replace").strip()))
        return found, False
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
        process.stderr.close()


def main():
    store = Store(sys.argv[1])
    try:
        for line in sys.stdin:
            request = json.loads(line)
            try:
                result = store.dispatch(request)
                response = {"id": request["id"], "result": result}
            except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
                response = {"id": request["id"], "error": str(error)}
            print(json.dumps(response, ensure_ascii=True), flush=True)
    finally:
        store.db.close()


if __name__ == "__main__":
    main()
