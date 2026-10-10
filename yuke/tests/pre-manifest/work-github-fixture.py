#!/usr/bin/env python3
"""Isolated gh substitute. Reject commands other than repository reads and GraphQL queries."""
import json
import os
from pathlib import Path
import sys
import time

args = sys.argv[1:]
if os.environ.get("GH_FIXTURE_LOG"):
    with open(os.environ["GH_FIXTURE_LOG"], "a") as log:
        log.write(json.dumps(args) + "\n")
if os.environ.get("GH_FIXTURE_FAIL"):
    print("HTTP 401: Requires authentication. Run gh auth login.", file=sys.stderr)
    sys.exit(1)
if args[:2] == ["repo", "view"]:
    assert "GH_REPO" not in os.environ, "the calling project must not inherit a foreign GH_REPO override"
    print(json.dumps({"nameWithOwner": "example/repo", "url": "https://github.com/example/repo"}))
    sys.exit(0)
assert args[:2] == ["api", "graphql"], "only reads are allowed"
fields = dict(arg.split("=", 1) for arg in args if "=" in arg)
query = fields["query"]
assert query.startswith("query(") and "mutation" not in query.lower(), "GitHub writes are forbidden"
assert fields["owner"] == "example" and fields["name"] == "repo"
kind = "pulls" if "pullRequest" in query else "issues"
get = "number" in fields
slow = os.environ.get("GH_FIXTURE_SLOW_FILE")
if get and slow and Path(slow).exists():
    Path(slow + ".pid").write_text(str(os.getpid()))
    time.sleep(12)

def record(number, kind):
    return {"number": number, "title": "Repair navigation" if number == 17 else "Review focus PR" if kind == "pulls" else f"Issue {number}",
            "url": f"https://github.com/example/repo/{'pull' if kind == 'pulls' else 'issues'}/{number}",
            "state": "OPEN", "updatedAt": "2026-10-12T12:00:00Z", "author": {"login": "reviewer"},
            "labels": {"nodes": [{"name": "bug"}]}, "body": "Read-only remote body\nKeep inner steps separate from GitHub state.\x1b[31m",
            **({"isDraft": False, "reviewDecision": "CHANGES_REQUESTED", "headRefName": "fix-focus", "baseRefName": "main",
                "statusCheckRollup": {"state": "FAILURE", "contexts": {"nodes": [{"name": "test", "status": "COMPLETED", "conclusion": "FAILURE", "detailsUrl": "https://github.com/example/repo/actions/runs/1"}, {"context": "lint", "state": "SUCCESS", "targetUrl": ""}], "pageInfo": {"hasNextPage": False}}}} if kind == "pulls" else {})}

if get:
    number = int(fields["number"])
    result = record(number, kind)
    if number == 999:
        result = None
    connection = "pullRequest" if kind == "pulls" else "issue"
else:
    start = int(fields.get("cursor", "0"))
    numbers = [18] if kind == "pulls" else [17] + list(range(100, 122))
    records = [record(number, kind) for number in numbers]
    if "states: [CLOSED" in query:
        for raw in records:
            raw["state"] = "MERGED" if kind == "pulls" else "CLOSED"
    result = {"nodes": records[start:start + 20], "totalCount": len(records), "pageInfo": {"endCursor": str(start + 20), "hasNextPage": start + 20 < len(records)}}
    connection = "pullRequests" if kind == "pulls" else "issues"
print(json.dumps({"data": {"repository": {connection: result}}}))
