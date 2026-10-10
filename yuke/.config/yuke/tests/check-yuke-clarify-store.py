#!/usr/bin/env python3
"""Check persistence, deduplication, private storage, and cross-process claims."""
import json
import pathlib
import subprocess
import tempfile

HELPER = pathlib.Path(__file__).resolve().parents[1] / "plugins/yuke-clarify-store.py"
with tempfile.TemporaryDirectory(prefix="yuke-clarify-store-") as directory:
    database = pathlib.Path(directory) / "private/questions.sqlite3"

    def command(action, args=None):
        return ["python3", str(HELPER), str(database), action, json.dumps(args or {})]

    def run(action, args=None):
        return json.loads(subprocess.check_output(command(action, args), text=True))

    assert run("list") == []
    question = {"title": "Target", "question": "Where should it run?", "context": "Storage depends on this.", "options": []}
    first = run("add", {"site": "one:1:1", "session": "one", "question": question})
    assert run("add", {"site": "one:1:1", "session": "one", "question": question})["id"] == first["id"]
    assert run("add", {"site": "one:2:1", "session": "one", "question": question})["id"] == first["id"]
    other = run("add", {"site": "two:1:1", "session": "two", "question": question})
    assert other["id"] != first["id"]
    draft = {"text": "partially written", "selected": 1, "other": True}
    run("draft", {"id": first["id"], "draft": draft})
    assert run("list")[0]["draft"] == draft
    args = {"id": first["id"], "kind": "answered", "answer": "Local"}
    processes = [subprocess.Popen(command("claim", args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    results = [(process.communicate(), process.returncode) for process in processes]
    assert sorted(code for _, code in results) == [0, 1], results
    claim = json.loads(next(output[0] for output, code in results if code == 0))
    assert run("list")[0]["status"] == "sending", "crashed sends must not be automatically retried"
    assert run("add", {"site": "one:3:1", "session": "one", "question": question})["id"] == first["id"]
    rejected = subprocess.run(command("finish", {"id": first["id"], "token": "not-owner", "input_id": "input"}), capture_output=True)
    assert rejected.returncode == 1
    run("release", {"id": first["id"], "token": claim["token"], "error": "engine refused"})
    assert run("list")[0]["status"] == "pending"
    claim = run("claim", args)
    run("finish", {"id": first["id"], "token": claim["token"], "input_id": "accepted-input"})
    assert [item["id"] for item in run("list")] == [other["id"]]
    assert subprocess.run(command("claim", args), capture_output=True).returncode == 1
    declined = run("claim", {"id": other["id"], "kind": "dismissed", "answer": ""})
    run("finish", {"id": other["id"], "token": declined["token"], "input_id": "declined-input"})
    assert run("list") == []
    assert database.stat().st_mode & 0o777 == 0o600
    assert database.parent.stat().st_mode & 0o777 == 0o700
print("Clarification store checks passed")
