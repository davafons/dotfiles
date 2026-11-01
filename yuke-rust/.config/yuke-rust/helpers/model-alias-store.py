#!/usr/bin/env python3
"""Save model aliases atomically. A revision check prevents lost concurrent edits."""
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import tempfile

LIMIT = 65536


def validate(value):
    if not isinstance(value, dict) or set(value) != {"version", "revision", "presets"}:
        raise ValueError("Invalid model alias file")
    if type(value["version"]) is not int or value["version"] != 1 or type(value["revision"]) is not int or value["revision"] < 0:
        raise ValueError("Invalid model alias version")
    rows = value["presets"]
    if not isinstance(rows, list) or len(rows) > 64:
        raise ValueError("At most 64 model aliases are allowed")
    aliases = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) - {"alias", "model", "latest", "effort", "key"}:
            raise ValueError("Invalid model alias entry")
        alias = row.get("alias")
        if not isinstance(alias, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", alias) or alias in aliases:
            raise ValueError("Invalid or duplicate model alias")
        aliases.add(alias)
        if ("model" in row) == ("latest" in row):
            raise ValueError("Set model or latest for each alias")
        for key in ("model", "effort", "key"):
            if key in row and (not isinstance(row[key], str) or len(row[key]) > 256 or
                               any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in row[key])):
                raise ValueError("Invalid model alias " + key)
        if "model" in row and not row["model"]:
            raise ValueError("Missing model selector")
        if "latest" in row:
            family = row["latest"]
            if not isinstance(family, dict) or set(family) != {"provider", "family"} or family["family"] not in ("sol", "luna"):
                raise ValueError("Invalid latest model family")
            if not isinstance(family["provider"], str) or not family["provider"] or len(family["provider"]) > 256 or any(ord(c) < 32 for c in family["provider"]):
                raise ValueError("Invalid latest model provider")
    return value


def save(path, request):
    path = Path(path)
    validate(request)
    encoded = json.dumps({**request, "revision": request["revision"] + 1}, ensure_ascii=False, indent=2) + "\n"
    if len(encoded.encode()) > LIMIT:
        raise ValueError("Model aliases exceed 64 KiB")
    os.umask(0o077)
    lock = path.with_name(path.name + ".lock")
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        if path.is_symlink():
            raise ValueError("Model alias file must not be a symlink")
        current = 0
        if path.exists():
            with path.open("rb") as source:
                contents = source.read(LIMIT + 1)
            if len(contents) > LIMIT:
                raise ValueError("Model aliases exceed 64 KiB")
            current = validate(json.loads(contents))["revision"]
        if current != request["revision"]:
            raise ValueError("Model aliases changed in another Yuke. Reopen /model and try again.")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".model-alias-", delete=False) as output:
                temporary = output.name
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
            temporary = None
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if temporary is not None:
                os.unlink(temporary)
    return json.loads(encoded)


if __name__ == "__main__":
    try:
        print(json.dumps(save(sys.argv[1], json.loads(sys.argv[2]))))
    except (OSError, ValueError, IndexError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
