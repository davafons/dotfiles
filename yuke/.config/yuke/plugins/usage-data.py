#!/usr/bin/env python3
"""Read a consistent, read-only snapshot of Yuke's local usage history."""
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import sqlite3

TOKEN_FIELDS = ("input", "output", "reasoning", "cache_read", "cache_write")


def bucket(name=""):
    return dict(name=name, **{key: 0 for key in TOKEN_FIELDS}, cost=0.0,
                withoutCache=0.0, unpriced=0, unreported=0, messages=0, tools=0)


def add_usage(target, message):
    target["messages"] += 1
    tokens = message.get("tokens")
    if tokens is None:
        target["unreported"] += 1
        return
    # Yuke includes cache tokens in input and reasoning tokens in output.
    for key in TOKEN_FIELDS:
        target[key] += tokens.get(key, 0)
    cost = message.get("cost")
    if cost is None:
        target["unpriced"] += 1
    else:
        target["cost"] += cost["total"]
        target["withoutCache"] += cost["without_cache"]


def ranked(values, field):
    return sorted(values, key=lambda item: (-item[field], item["name"]))


def streaks(days, today):
    dates = sorted(date.fromisoformat(day) for day in days)
    longest = length = 0
    previous = None
    for day in dates:
        length = length + 1 if previous and day == previous + timedelta(days=1) else 1
        longest = max(longest, length)
        previous = day
    cursor = today if today.isoformat() in days else today - timedelta(days=1)
    current = 0
    while cursor.isoformat() in days:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest


def snapshot(database, workspace=None, now=None):
    now = now or datetime.now().astimezone()
    db = sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only = ON")
        db.execute("BEGIN")
        condition = "WHERE s.root = ?" if workspace else ""
        params = (workspace,) if workspace else ()
        sessions = {}
        totals = bucket()
        for row in db.execute(f"SELECT s.* FROM sessions s {condition}", params):
            sid = row["id"].hex()
            sessions[sid] = dict(id=sid, title=row["title"] or row["name"] or "Untitled chat",
                                 root=row["root"], kind=row["origin"], model=row["model"],
                                 created=row["created_at_ms"], updated=row["updated_at_ms"],
                                 messages=0, input=row["usage_input_total"], output=row["usage_output_total"],
                                 cost=row["cost_total"], unpriced=row["unpriced_count"],
                                 activeMs=0, elapsedMs=0, firstMessage=None, lastMessage=None)
            for key in TOKEN_FIELDS:
                totals[key] += row[f"usage_{key}_total"]
            totals["cost"] += row["cost_total"]
            totals["withoutCache"] += row["cost_without_cache_total"]
            totals["unpriced"] += row["unpriced_count"]

        configs = {(row["sid"].lower(), row["config_rev"]): (row["model"], row["reasoning"])
                   for row in db.execute(f"""
                       SELECT hex(c.session_id) sid, c.config_rev, c.model, c.reasoning
                       FROM session_configs c JOIN sessions s ON s.id = c.session_id {condition}
                   """, params)}
        catalog = defaultdict(dict)
        catalog_names = set()
        for row in db.execute(f"""
            SELECT hex(k.session_id) sid, k.name, k.path, k.canonical_path
            FROM session_skills k JOIN sessions s ON s.id = k.session_id {condition}
        """, params):
            sid = row["sid"].lower()
            catalog_names.add(row["name"])
            for path in (row["path"], row["canonical_path"]):
                catalog[sid][os.path.normpath(path)] = row["name"]

        daily = defaultdict(bucket)
        models = defaultdict(bucket)
        providers = defaultdict(bucket)
        roles = Counter()
        finishes = Counter()
        outcomes = Counter()
        efforts = Counter()
        observed = bucket()
        skills = {}
        seen_skills = set()
        pending_skills = defaultdict(list)
        active_days = set()
        completed_runs = 0

        def skill_use(sid, run, name, source):
            item = skills.setdefault(name, dict(name=name, uses=0, invocations=0, reads=0))
            item[source] += 1
            key = (sid, run, name)
            if key not in seen_skills:
                seen_skills.add(key)
                item["uses"] += 1

        for row in db.execute(f"""
            SELECT hex(e.session_id) sid, e.seq, e.name, e.committed_at_ms,
                   json_remove(e.payload, '$.content', '$.summary') metadata
            FROM events e JOIN sessions s ON s.id = e.session_id
            {condition}
            ORDER BY e.session_id, e.seq
        """, params):
            sid = row["sid"].lower()
            meta = json.loads(row["metadata"])
            chat = sessions[sid]
            if row["name"] == "run.started":
                for name in pending_skills.pop(sid, []):
                    skill_use(sid, meta["run_id"], name, "invocations")
            elif row["name"] == "run.done":
                timing = meta["timing"]
                chat["activeMs"] += max(0, timing["ended_at_ms"] - timing["started_at_ms"])
                completed_runs += 1
                outcomes[meta["outcome"]["type"]] += 1
            elif row["name"] == "message.committed":
                role = meta["type"]
                timestamp = meta["time"]["created_at_ms"]
                chat["messages"] += 1
                chat["firstMessage"] = timestamp if chat["firstMessage"] is None else min(chat["firstMessage"], timestamp)
                ended = meta["time"].get("completed_at_ms", timestamp)
                chat["lastMessage"] = ended if chat["lastMessage"] is None else max(chat["lastMessage"], ended)
                roles["engine" if role == "user" and meta.get("source") else role] += 1
                if role == "user" and meta.get("skill_name"):
                    pending_skills[sid].append(meta["skill_name"])
                if role != "assistant":
                    continue
                day = datetime.fromtimestamp(timestamp / 1000).astimezone().date().isoformat()
                active_days.add(day)
                finishes[meta.get("finish", "unknown")] += 1
                model, effort = configs.get((sid, meta.get("config_rev")), ("Unknown", "Unknown"))
                model = meta.get("provenance", {}).get("model", model)
                provider = model.split("/", 1)[0] if "/" in model else "Unknown"
                efforts[effort or "default"] += 1
                add_usage(observed, meta)
                add_usage(daily[day], meta)
                add_usage(models[model], meta)
                add_usage(providers[provider], meta)

        tools = {}
        for row in db.execute(f"""
            SELECT hex(e.session_id) sid, json_extract(e.payload, '$.run_id') run_id,
                   json_extract(e.payload, '$.time.created_at_ms') created_at_ms,
                   json_extract(p.value, '$.name') name,
                   json_extract(p.value, '$.arguments') arguments,
                   json_extract(p.value, '$.state.type') state,
                   json_extract(p.value, '$.state.duration_ms') duration_ms
            FROM events e JOIN sessions s ON s.id = e.session_id,
                 json_each(e.payload, '$.content') p
            {condition + ' AND' if condition else 'WHERE'} e.name = 'message.committed'
              AND json_extract(e.payload, '$.type') = 'assistant'
              AND json_extract(p.value, '$.type') = 'tool'
        """, params):
            sid = row["sid"].lower()
            name = row["name"]
            item = tools.setdefault(name, dict(name=name, calls=0, errors=0, canceled=0, durationMs=0))
            item["calls"] += 1
            item["errors"] += row["state"] == "error"
            item["canceled"] += row["state"] == "canceled"
            item["durationMs"] += row["duration_ms"] or 0
            day = datetime.fromtimestamp(row["created_at_ms"] / 1000).astimezone().date().isoformat()
            daily[day]["tools"] += 1
            if row["state"] != "completed":
                continue
            try:
                arguments = json.loads(row["arguments"])
            except (ValueError, TypeError):
                continue
            if not isinstance(arguments, dict):
                continue
            if name == "skill" and isinstance(arguments.get("name"), str) and arguments["name"]:
                skill_use(sid, row["run_id"], arguments["name"], "invocations")
            elif name == "read" and isinstance(arguments.get("path"), str):
                path = os.path.expanduser(arguments["path"])
                if not os.path.isabs(path):
                    path = os.path.join(sessions[sid]["root"], path)
                skill = catalog[sid].get(os.path.normpath(path))
                if skill:
                    skill_use(sid, row["run_id"], skill, "reads")

        for sid, names in pending_skills.items():
            for index, name in enumerate(names):
                skill_use(sid, f"pending-{index}", name, "invocations")
        for chat in sessions.values():
            if chat["firstMessage"] is not None:
                chat["elapsedMs"] = max(0, chat["lastMessage"] - chat["firstMessage"])
            del chat["firstMessage"], chat["lastMessage"]
        totals["messages"] = observed["messages"]
        totals["unreported"] = observed["unreported"]
        totals["tools"] = sum(item["calls"] for item in tools.values())
        current, longest = streaks(active_days, now.date())
        chats = sorted(sessions.values(), key=lambda item: (-item["updated"], item["id"]))
        top_level = [chat for chat in chats if chat["kind"] != "child"]
        notes = []
        if any(totals[key] != observed[key] for key in TOKEN_FIELDS):
            notes.append("Lifetime totals include usage no longer present in the event history. Breakdowns cover retained events.")
        return dict(asOf=now.isoformat(), scope=workspace, totals=totals, roles=dict(roles),
                    finishes=dict(finishes), outcomes=dict(outcomes),
                    daily=[dict(value, date=key) for key, value in sorted(daily.items())],
                    models=ranked([dict(value, name=key) for key, value in models.items()], "input"),
                    providers=ranked([dict(value, name=key) for key, value in providers.items()], "input"),
                    efforts=[dict(name=key, count=value) for key, value in efforts.most_common()],
                    tools=ranked(tools.values(), "calls"), skills=ranked(skills.values(), "uses"),
                    catalogSkills=len(catalog_names), chats=chats,
                    chatCount=len(top_level), childCount=len(chats) - len(top_level),
                    activeMs=sum(chat["activeMs"] for chat in chats), completedRuns=completed_runs,
                    longestChatMs=max((chat["elapsedMs"] for chat in top_level), default=0),
                    currentStreak=current, longestStreak=longest, notes=notes)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    parser.add_argument("--workspace")
    parser.add_argument("--output", help="Write JSON to a new private file instead of stdout")
    args = parser.parse_args()
    try:
        result = snapshot(args.database, args.workspace)
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(result, output, separators=(",", ":"))
        else:
            print(json.dumps(result, separators=(",", ":")))
    except (sqlite3.Error, OSError, KeyError, ValueError) as error:
        parser.exit(1, f"Cannot read Yuke usage history: {error}\n")


if __name__ == "__main__":
    main()
