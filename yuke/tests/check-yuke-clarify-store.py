#!/usr/bin/env python3
"""Check persistence, deduplication, private storage, and cross-process claims."""
import json
import pathlib
import subprocess
import tempfile

HELPER = pathlib.Path(__file__).resolve().parents[1] / ".config/yuke/plugins/yuke-clarify-store.py"
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
    assert run("add", {"site": "one:legacy:1", "session": "one", "question": {**question, "multi_select": False}})["id"] == first["id"]
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
    batch_questions = [
        {"title": "Features", "question": "Which features?", "context": "", "options": [], "multi_select": True, "question_id": "features"},
        {"title": "Owner", "question": "Who owns it?", "context": "", "options": [], "multi_select": False, "question_id": "owner"},
    ]
    batch = run("add_batch", {"site": "one:batch:1", "session": "one", "questions": batch_questions})
    assert run("add_batch", {"site": "one:batch:2", "session": "one", "questions": batch_questions})["id"] == batch["id"]
    multi_draft = {"text": "Both please", "selected": 1, "other": False, "checked": [0, 1], "notes": True,
                   "committed": True, "responses": ["Logging", "Metrics", "user_note: Both please"]}
    run("draft", {"id": batch["questions"][0]["id"], "draft": multi_draft})
    assert run("list")[0]["draft"] == multi_draft
    assert run("list")[0]["batch_id"] == batch["id"]
    assert subprocess.run(command("claim_batch", {"id": batch["id"]}), capture_output=True).returncode == 1, "unanswered questions require explicit confirmation"
    run("draft", {"id": batch["questions"][1]["id"], "draft": {"text": "Ops", "selected": 0, "other": False, "committed": True, "responses": ["user_note: Ops"]}})
    processes = [subprocess.Popen(command("claim_batch", {"id": batch["id"]}), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    results = [(process.communicate(), process.returncode) for process in processes]
    assert sorted(code for _, code in results) == [0, 1]
    claim = json.loads(next(output[0] for output, code in results if code == 0))
    assert claim["answers"] == {"features": {"answers": multi_draft["responses"]}, "owner": {"answers": ["user_note: Ops"]}}
    assert all(item["status"] == "sending" for item in run("list"))
    assert subprocess.run(command("finish_batch", {"id": batch["id"], "token": "not-owner", "input_id": "input"}), capture_output=True).returncode == 1
    run("release_batch", {"id": batch["id"], "token": claim["token"], "error": "engine refused"})
    claim = run("claim_batch", {"id": batch["id"]})
    run("finish_batch", {"id": batch["id"], "token": claim["token"], "input_id": "batch-input"})
    assert run("list") == []
    skipped = run("add_batch", {"site": "one:skip:1", "session": "one", "questions": batch_questions})
    claim = run("claim_batch", {"id": skipped["id"], "allow_unanswered": True})
    assert all(answer["answers"] == [] for answer in claim["answers"].values())
    assert len(run("list")) == 2, "crashed batch sends remain reserved"
    run("finish_batch", {"id": skipped["id"], "token": claim["token"], "input_id": "skip-input"})
    assert run("list") == []
print("Clarification store checks passed (single and batch persistence, claims, migration compatibility)")
