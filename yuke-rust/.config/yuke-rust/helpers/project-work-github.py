#!/usr/bin/env python3
"""Read project GitHub metadata through gh. This helper sends GraphQL queries, never mutations."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

COMMON = "number title url state updatedAt author { login } labels(first: 6) { nodes { name } }"
PULL = "isDraft reviewDecision statusCheckRollup { state }"
CHECKS = "statusCheckRollup { state contexts(first: 20) { nodes { ... on CheckRun { name status conclusion detailsUrl } ... on StatusContext { context state targetUrl } } pageInfo { hasNextPage } } }"


def gh(root, *args):
    try:
        result = subprocess.run(["gh", *args], cwd=root, env={key: value for key, value in os.environ.items() if key != "GH_REPO"}, capture_output=True, text=True, timeout=25)
    except FileNotFoundError:
        raise ValueError("Install the GitHub CLI (gh) to read GitHub work") from None
    if result.returncode:
        raise ValueError(result.stderr.strip() or "GitHub read failed")
    return json.loads(result.stdout)


def clean(value):
    return re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", " ", value or "")


def item(raw, kind):
    rollup = raw.get("statusCheckRollup") or {}
    checks = []
    for check in rollup.get("contexts", {}).get("nodes", []):
        checks.append({"name": clean(check.get("name") or check.get("context")),
                       "status": clean(check.get("conclusion") or check.get("state") or check.get("status")),
                       "url": clean(check.get("detailsUrl") or check.get("targetUrl"))})
    return {"number": raw["number"], "title": " ".join(clean(raw["title"]).split()),
            "url": raw["url"], "state": raw["state"], "updated_at": raw["updatedAt"],
            "author": clean((raw.get("author") or {}).get("login")),
            "labels": [clean(label["name"]) for label in raw["labels"]["nodes"]],
            "kind": kind, "draft": raw.get("isDraft", False), "review": raw.get("reviewDecision"),
            "ci": rollup.get("state"), "body": clean(raw.get("body", "")), "checks": checks,
            "more_checks": rollup.get("contexts", {}).get("pageInfo", {}).get("hasNextPage", False),
            "head": clean(raw.get("headRefName")), "base": clean(raw.get("baseRefName"))}


def read(args):
    if not isinstance(args, dict) or set(args) - {"root", "repo", "action", "kind", "state", "cursor", "number"}:
        raise ValueError("unknown GitHub read field")
    root = Path(args["root"]).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("project root must be a directory")
    action = args.get("action")
    kind = args.get("kind", "issues")
    state = args.get("state", "open")
    cursor = args.get("cursor", "")
    if action not in ("list", "get") or kind not in ("issues", "pulls") or state not in ("open", "closed", "all"):
        raise ValueError("invalid GitHub read action, kind, or state")
    if not isinstance(cursor, str) or len(cursor) > 1000 or any(ord(c) < 32 for c in cursor):
        raise ValueError("invalid GitHub cursor")
    number = args.get("number")
    if action == "get" and (type(number) is not int or number < 1):
        raise ValueError("get requires a positive issue or PR number")
    repo = args.get("repo")
    if repo is None:
        metadata = gh(root, "repo", "view", "--json", "nameWithOwner,url")
        if not metadata["url"].startswith("https://github.com/"):
            raise ValueError("This GitHub view supports github.com repositories only")
        repo = metadata["nameWithOwner"]
    if not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+", repo):
        raise ValueError("invalid project GitHub repository")
    owner, name = repo.split("/")
    fields = COMMON + (" " + PULL if kind == "pulls" and action == "list" else "")
    if action == "list":
        states = {"open": "[OPEN]", "closed": "[CLOSED, MERGED]" if kind == "pulls" else "[CLOSED]", "all": "null"}[state]
        connection = "issues" if kind == "issues" else "pullRequests"
        selection = f"{connection}(first: 20, after: $cursor, states: {states}, orderBy: {{field: UPDATED_AT, direction: DESC}}) {{ totalCount nodes {{ {fields} }} pageInfo {{ endCursor hasNextPage }} }}"
        query = "query($owner: String!, $name: String!, $cursor: String) { repository(owner: $owner, name: $name) { " + selection + " } }"
    else:
        selection = "issue" if kind == "issues" else "pullRequest"
        if kind == "pulls":
            fields += " isDraft reviewDecision headRefName baseRefName " + CHECKS
        query = "query($owner: String!, $name: String!, $number: Int!) { repository(owner: $owner, name: $name) { " + selection + "(number: $number) { " + fields + " body } } }"
    command = ["api", "graphql", "--hostname", "github.com", "-f", "query=" + query, "-f", "owner=" + owner, "-f", "name=" + name]
    command.extend(["-F", "number=" + str(number)] if action == "get" else ["-f", "cursor=" + cursor] if cursor else [])
    reply = gh(root, *command)
    if reply.get("errors"):
        raise ValueError("; ".join(error["message"] for error in reply["errors"]))
    repository = reply["data"]["repository"]
    if repository is None:
        raise ValueError("GitHub repository is unavailable to these credentials")
    result = {"repo": repo, "repo_url": "https://github.com/" + repo, "kind": kind, "fetched_at": int(time.time() * 1000)}
    if action == "get":
        raw = repository[selection]
        if raw is None:
            raise ValueError("GitHub item was not found in this project")
        result["item"] = item(raw, kind)
    else:
        page = repository[connection]
        result.update(items=[item(raw, kind) for raw in page["nodes"]], total=page["totalCount"],
                      next_cursor=page["pageInfo"]["endCursor"] or "", has_next=page["pageInfo"]["hasNextPage"], state=state)
    return result


if __name__ == "__main__":
    try:
        print(json.dumps(read(json.loads(sys.argv[1])), ensure_ascii=False))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
