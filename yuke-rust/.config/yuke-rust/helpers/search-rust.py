#!/usr/bin/env python3
"""Drive the search index with one private file request. Session history comes from the public Rust API."""
import importlib.util
import json
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location("search_store", Path(__file__).with_name("search-store.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
request = json.loads(Path(sys.argv[2]).read_text())
store = module.Store(sys.argv[1])
try:
    if request["action"] == "index":
        store.begin(request["session_id"])
        for part in request["parts"]:
            store.part(part)
        result = store.finish(request["session_id"], request["signature"])
    else:
        result = store.dispatch(request)
    print(json.dumps(result))
finally:
    store.db.close()
