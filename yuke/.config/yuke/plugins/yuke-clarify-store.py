#!/usr/bin/env python3
"""Private, transactional clarification inbox. One short-lived process per operation."""
import json
import os
import pathlib
import sqlite3
import sys
import time
import uuid


def operate(path, action, args):
    os.umask(0o077)
    directory = pathlib.Path(path).parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if pathlib.Path(path).is_symlink():
        raise ValueError("clarification database must not be a symlink")
    with sqlite3.connect(path, timeout=10) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS questions (
            id TEXT PRIMARY KEY, session TEXT NOT NULL, site TEXT UNIQUE NOT NULL,
            fingerprint TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL)""")
        db.execute("BEGIN IMMEDIATE")
        if action == "list":
            return [json.loads(row[0]) for row in db.execute(
                "SELECT data FROM questions WHERE status IN ('pending', 'sending') ORDER BY rowid")]
        if action == "add":
            question = args["question"]
            fingerprint = json.dumps(question, sort_keys=True, ensure_ascii=False)
            existing = db.execute(
                "SELECT data FROM questions WHERE site=? OR (session=? AND fingerprint=? AND status='pending') LIMIT 1",
                (args["site"], args["session"], fingerprint)).fetchone()
            if existing:
                return json.loads(existing[0])
            record = dict(question, id="q-" + uuid.uuid4().hex[:16], session=args["session"],
                          status="pending", created=int(time.time() * 1000),
                          draft={"text": "", "selected": 0, "other": False})
            db.execute("INSERT INTO questions VALUES (?, ?, ?, ?, ?, ?)",
                       (record["id"], record["session"], args["site"], fingerprint, "pending", json.dumps(record)))
            return record
        row = db.execute("SELECT data FROM questions WHERE id=?", (args["id"],)).fetchone()
        if not row:
            raise ValueError("question no longer exists")
        record = json.loads(row[0])
        if action == "draft":
            if record["status"] == "pending":
                record["draft"] = args["draft"]
        elif action == "claim":
            if record["status"] != "pending":
                raise ValueError("question already answered or delivery is in progress")
            if args["kind"] not in ("answered", "dismissed"):
                raise ValueError("invalid answer kind")
            if args["kind"] == "answered" and not args["answer"].strip():
                raise ValueError("answer must not be empty")
            record.update(status="sending", token=uuid.uuid4().hex,
                          answer=args["answer"], kind=args["kind"])
            record.pop("error", None)
        elif action in ("finish", "release"):
            if record["status"] != "sending" or record.get("token") != args["token"]:
                raise ValueError("delivery claim no longer belongs to this sender")
            if action == "finish":
                record.update(status=record["kind"], input_id=args["input_id"])
            else:
                record.update(status="pending", error=args["error"])
            record.pop("token", None)
        else:
            raise ValueError("unknown inbox operation")
        db.execute("UPDATE questions SET status=?, data=? WHERE id=?",
                   (record["status"], json.dumps(record), record["id"]))
        return record


if __name__ == "__main__":
    try:
        print(json.dumps(operate(sys.argv[1], sys.argv[2], json.loads(sys.argv[3])), ensure_ascii=False))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
