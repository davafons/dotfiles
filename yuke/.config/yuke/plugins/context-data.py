#!/usr/bin/env python3
"""Read saved prompt metadata without changing the session store."""
import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
import sqlite3


def snapshot(database, session_id):
    sid = bytes.fromhex(session_id)
    if len(sid) != 16:
        raise ValueError("Session ID must hold 32 hexadecimal characters.")
    db = sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only = ON")
        db.execute("BEGIN")
        session = db.execute("SELECT model, prompt_tokens FROM sessions WHERE id = ?", (sid,)).fetchone()
        if session is None:
            raise ValueError("The session is no longer in this store.")
        prompt = db.execute("SELECT generation FROM session_prompts WHERE session_id = ?", (sid,)).fetchone()
        sections = []
        size = 0
        skill_costs = {}
        skill_overhead = dict(bytes=0, tokens=0)
        for row in db.execute("SELECT key, length(CAST(text AS BLOB)) bytes, CASE WHEN key = 'skills' THEN text ELSE NULL END catalog FROM session_prompt_sections WHERE session_id = ? ORDER BY position", (sid,)):
            before = (size + 3) // 4
            if row["catalog"]:
                blocks = []
                for match in re.finditer(r"(?m)^  <skill>\n.*?^  </skill>\n?", row["catalog"], re.S):
                    try:
                        element = ET.fromstring(match.group())
                    except ET.ParseError:
                        continue
                    name = element.findtext("name")
                    if name:
                        blocks.append((name, len(match.group().encode("utf-8"))))
                skill_overhead["bytes"] = row["bytes"] - sum(count for _, count in blocks)
                cursor = size + (2 if size else 0) + skill_overhead["bytes"]
                skill_overhead["tokens"] = (cursor + 3) // 4 - before
                for name, count in blocks:
                    old = (cursor + 3) // 4
                    cursor += count
                    cost = skill_costs.setdefault(name, dict(bytes=0, tokens=0))
                    cost["bytes"] += count
                    cost["tokens"] += (cursor + 3) // 4 - old
            if row["bytes"]:
                size += row["bytes"] + (2 if size else 0)
            sections.append(dict(key=row["key"], bytes=row["bytes"], tokens=(size + 3) // 4 - before))
        system = (size + 3) // 4
        last = db.execute("SELECT model FROM messages WHERE session_id = ? AND role = 'assistant' AND model IS NOT NULL ORDER BY message_id DESC LIMIT 1", (sid,)).fetchone()
        # A stale prompt, changed model, or smaller budget cannot identify tool overhead.
        prompt_available = bool(prompt and last and last["model"] == session["model"] and system > 0)
        stale = bool(prompt and prompt["generation"] == 0)
        valid = bool(prompt_available and not stale and session["prompt_tokens"] >= system and session["prompt_tokens"] > 0)
        sources = [dict(row) for row in db.execute("SELECT scope, path FROM session_instructions WHERE session_id = ? ORDER BY scope, path", (sid,))]
        metadata = {row["name"]: dict(row) for row in db.execute("SELECT name, scope, description FROM session_skills WHERE session_id = ? ORDER BY name", (sid,))}
        skills = []
        for name in metadata.keys() | skill_costs.keys():
            skill = metadata.get(name, dict(name=name, scope="saved", description=""))
            skill.update(skill_costs.get(name, dict(bytes=None, tokens=None)))
            skills.append(skill)
        skills.sort(key=lambda skill: (-(skill["tokens"] or 0), skill["name"]))
        return dict(model=session["model"], sections=sections, system=system,
                    fixed=session["prompt_tokens"], tools=session["prompt_tokens"] - system if valid else None,
                    valid=valid, promptAvailable=prompt_available, stale=stale, sources=sources, skills=skills, skillOverhead=skill_overhead)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    parser.add_argument("session_id")
    args = parser.parse_args()
    print(json.dumps(snapshot(args.database, args.session_id), ensure_ascii=False))


if __name__ == "__main__":
    main()
