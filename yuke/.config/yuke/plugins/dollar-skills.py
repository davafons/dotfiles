#!/usr/bin/env python3
"""Scan Yuke skill roots. Output JSON; use no third-party modules."""
import json
import os
import pathlib
import re
import stat
import sys


def scalar(value):
    if not value:
        return value
    if value[0] == "'":
        match = re.match(r"'((?:[^']|'')*)'", value)
        return match[1].replace("''", "'") if match else value
    if value[0] == '"':
        out = []
        i = 1
        escapes = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "a": "\a", "b": "\b", "e": "\x1b", "f": "\f", "v": "\v"}
        while i < len(value):
            char = value[i]
            if char == '"':
                return "".join(out)
            if char == "\\":
                i += 1
                if i == len(value):
                    return value
                char = value[i]
                digits = {"x": 2, "u": 4, "U": 8}.get(char, 0)
                if digits:
                    encoded = value[i + 1:i + 1 + digits]
                    if len(encoded) != digits or not re.fullmatch(r"[0-9a-fA-F]+", encoded):
                        return value
                    code = int(encoded, 16)
                    if code > 0x10FFFF or 0xD800 <= code <= 0xDFFF:
                        return value
                    char = chr(code)
                    i += digits
                else:
                    char = escapes.get(char, char)
            out.append(char)
            i += 1
        return value
    return value.split(" #", 1)[0].rstrip(" \t")


def frontmatter(text):
    lines = text.split("\n")
    if lines[0].rstrip(" \t\r") != "---":
        raise ValueError("the file has no frontmatter")
    fields = {}
    for i in range(1, len(lines)):
        line = lines[i].rstrip("\r")
        if line.rstrip(" \t") == "---":
            return fields, "\n".join(lines[i + 1:]).strip(" \t\r\n")
        if not line or line[0] in " \t#" or ":" not in line:
            continue
        key, raw = line.split(":", 1)
        key, raw = key.strip(" \t"), raw.strip(" \t")
        if key not in ("name", "description"):
            continue
        if re.fullmatch(r"[|>][-+]?", raw):
            out = ""
            indent = None
            pending = 0
            previous_more = False
            first = True
            for following in lines[i + 1:]:
                following = following.rstrip("\r")
                stripped = following.lstrip(" ")
                if not stripped.strip(" \t"):
                    pending += 1
                    continue
                width = len(following) - len(stripped)
                if indent is None:
                    indent = width
                if indent == 0 or width < indent:
                    break
                content = following[indent:]
                more = content.startswith(" ")
                if not first:
                    fold = raw[0] == ">" and not more and not previous_more
                    out += " " if fold and pending == 0 else "\n" * (pending if fold else pending + 1)
                out += content
                first, pending, previous_more = False, 0, more
            value = out
        else:
            value = scalar(raw)
        fields[key] = value.rstrip(" \t\r\n")
    raise ValueError("the file has no closing frontmatter delimiter")


def read_header(path):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK), "rb") as file:
        info = os.fstat(file.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("the source is not a regular file")
        if info.st_size > 256 * 1024:
            raise ValueError("the file exceeds 256 KiB")
        return file.read(16 * 1024).decode("utf-8", errors="surrogateescape")


def scan(workspace):
    entries = {}
    canonical_seen = set()
    roots = [pathlib.Path(workspace) / ".agents/skills", pathlib.Path.home() / ".agents/skills"]
    for root, scope in zip(roots, ("workspace", "global")):
        if not root.is_dir():
            continue
        names = sorted(root.iterdir())
        if len(names) > 1024:
            raise ValueError("the skill root exceeds 1024 entries")
        candidates = 0
        for directory in names:
            path = directory / "SKILL.md"
            if not path.exists():
                continue
            candidates += 1
            if candidates > 256:
                raise ValueError("the skill root exceeds 256 candidates")
            try:
                canonical = str(path.resolve(strict=True))
                canonical.encode("utf-8")
                if canonical in canonical_seen:
                    continue
                fields, _ = frontmatter(read_header(canonical))
                name = fields.get("name", directory.name)
                description = fields.get("description", "")
                name.encode("utf-8")
                description.encode("utf-8")
                if len(name) > 64 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
                    continue
                if not description.strip(" \t") or len(description) > 1024:
                    continue
                if any(ord(char) < 32 and char not in "\t\r\n" for char in description):
                    continue
                if name in entries:
                    continue
                entries[name] = dict(name=name, description=description, path=str(path), canonical_path=canonical, scope=scope)
                canonical_seen.add(canonical)
            except (OSError, ValueError):
                continue
    return sorted(entries.values(), key=lambda entry: entry["name"])


if __name__ == "__main__":
    try:
        if sys.argv[1] == "scan":
            print(json.dumps(scan(sys.argv[2] if len(sys.argv) > 2 else os.getcwd())))
        else:
            raise ValueError("unknown skill action")
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
