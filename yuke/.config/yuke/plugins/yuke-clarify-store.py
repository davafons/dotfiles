#!/usr/bin/env python3
"""Private, transactional clarification inbox. One short-lived process per operation."""
import json
import os
import pathlib
import sqlite3
import sys
import time
import uuid


def fingerprint(question):
    normalized = dict(question)
    if not normalized.get("multi_select"):
        normalized.pop("multi_select", None)
    return json.dumps(normalized, sort_keys=True, ensure_ascii=False)


def new_draft():
    return {"text": "", "selected": 0, "other": False, "checked": [],
            "otherSelected": False, "notes": False, "committed": False, "responses": []}


def save_request(db, record):
    db.execute("UPDATE requests SET status=?, data=? WHERE id=?",
               (record["status"], json.dumps(record), record["id"]))


def batch_entries(record):
    return [dict(question, batch_id=record["id"], batch_size=len(record["questions"]),
                 batch_index=index, session=record["session"], status=record["status"])
            for index, question in enumerate(record["questions"])]


def operate(path, action, args):
    os.umask(0o077)
    directory = pathlib.Path(path).parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if pathlib.Path(path).is_symlink():
        raise ValueError("clarification database must not be a symlink")
    with sqlite3.connect(path, timeout=10) as db:
        for table in ("questions", "requests"):
            db.execute(f"""CREATE TABLE IF NOT EXISTS {table} (
                id TEXT PRIMARY KEY, session TEXT NOT NULL, site TEXT UNIQUE NOT NULL,
                fingerprint TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL)""")
        db.execute("BEGIN IMMEDIATE")
        if action == "list":
            questions = [json.loads(row[0]) for row in db.execute(
                "SELECT data FROM questions WHERE status IN ('pending', 'sending') ORDER BY rowid")]
            for row in db.execute("SELECT data FROM requests WHERE status IN ('pending', 'sending') ORDER BY rowid"):
                questions.extend(batch_entries(json.loads(row[0])))
            return sorted(questions, key=lambda question: question["created"])
        if action in ("add", "add_batch"):
            batch = action == "add_batch"
            table = "requests" if batch else "questions"
            contents = args["questions"] if batch else args["question"]
            canonical = json.dumps([fingerprint(question) for question in contents]) if batch else fingerprint(contents)
            existing = db.execute(
                f"SELECT data FROM {table} WHERE site=? OR (session=? AND fingerprint=? AND status IN ('pending', 'sending')) LIMIT 1",
                (args["site"], args["session"], canonical)).fetchone()
            if existing:
                return json.loads(existing[0])
            now = int(time.time() * 1000)
            ident = ("r-" if batch else "q-") + uuid.uuid4().hex[:16]
            if batch:
                record = {"id": ident, "session": args["session"], "status": "pending", "created": now,
                          "questions": [dict(question, id=ident + ":" + question["question_id"],
                                             created=now, draft=new_draft()) for question in contents]}
            else:
                record = dict(contents, id=ident, session=args["session"], status="pending",
                              created=now, draft=new_draft())
            db.execute(f"INSERT INTO {table} VALUES (?, ?, ?, ?, ?, ?)",
                       (ident, args["session"], args["site"], canonical, "pending", json.dumps(record)))
            return record
        if ":" in args["id"]:
            batch_id = args["id"].split(":", 1)[0]
            row = db.execute("SELECT data FROM requests WHERE id=?", (batch_id,)).fetchone()
            if not row:
                raise ValueError("question batch no longer exists")
            request = json.loads(row[0])
            record = next((question for question in request["questions"] if question["id"] == args["id"]), None)
            if not record:
                raise ValueError("question no longer exists")
            if action != "draft":
                raise ValueError("submit a question batch together, not one question at a time")
            if request["status"] == "pending":
                record["draft"] = args["draft"]
                save_request(db, request)
            return record
        batch = action.endswith("_batch")
        table = "requests" if batch else "questions"
        row = db.execute(f"SELECT data FROM {table} WHERE id=?", (args["id"],)).fetchone()
        if not row:
            raise ValueError("question no longer exists")
        record = json.loads(row[0])
        verb = action.removesuffix("_batch") if batch else action
        if verb == "draft":
            if record["status"] == "pending":
                record["draft"] = args["draft"]
        elif verb == "claim":
            if record["status"] != "pending":
                raise ValueError("question already answered or delivery is in progress")
            if batch:
                unanswered = [question for question in record["questions"] if not question["draft"].get("committed")]
                if unanswered and not args.get("allow_unanswered", False):
                    raise ValueError("confirm before submitting unanswered questions")
                record["answers"] = {
                    question["question_id"]: {"answers": question["draft"].get("responses", []) if question["draft"].get("committed") else []}
                    for question in record["questions"]
                }
            else:
                if args["kind"] not in ("answered", "dismissed"):
                    raise ValueError("invalid answer kind")
                if args["kind"] == "answered" and not args["answer"].strip():
                    raise ValueError("answer must not be empty")
                record.update(answer=args["answer"], kind=args["kind"], responses=args.get("responses", []))
            record.update(status="sending", token=uuid.uuid4().hex)
            record.pop("error", None)
        elif verb in ("finish", "release"):
            if record["status"] != "sending" or record.get("token") != args["token"]:
                raise ValueError("delivery claim no longer belongs to this sender")
            if verb == "finish":
                record.update(status="answered" if batch else record["kind"], input_id=args["input_id"])
            else:
                record.update(status="pending", error=args["error"])
            record.pop("token", None)
        else:
            raise ValueError("unknown inbox operation")
        db.execute(f"UPDATE {table} SET status=?, data=? WHERE id=?",
                   (record["status"], json.dumps(record), record["id"]))
        return record


if __name__ == "__main__":
    try:
        print(json.dumps(operate(sys.argv[1], sys.argv[2], json.loads(sys.argv[3])), ensure_ascii=False))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
