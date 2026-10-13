#!/usr/bin/env python3
"""Exercise native child routing and model receipts with a scripted localhost provider."""
import argparse
import http.server
import json
import os
from pathlib import Path
import re
import select
import shutil
import subprocess
import tempfile
import threading
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=Path(shutil.which("yuke") or "yuke"))
    parser.add_argument("--plugin", type=Path, default=Path(__file__).resolve().parents[1] / ".config/yuke/plugins/agent-tools")
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    source = args.plugin.resolve(strict=True)
    project = Path(__file__).resolve().parents[2]
    root = Path(tempfile.mkdtemp(prefix="yuke-agent-tools-")).resolve()
    root.chmod(0o700)
    print("Artifacts:", root, flush=True)
    for name in ("home", "work", "config/yuke", "data", "state", "cache"):
        (root / name).mkdir(parents=True)
    profile = root / "config/yuke"
    shutil.copytree(source, profile / "agent-tools")
    (profile / "config.json").write_text('{"plugins":["./agent-tools"]}')
    local_skills = root / "work/.agents/skills"
    local_skills.mkdir(parents=True)
    for name in ("verify-yuke-profile", "verify-herdr-profile", "verify-neovim-profile"):
        (local_skills / name).symlink_to(project / ".agents/skills" / name)
    global_skills = root / "home/.agents/skills"
    global_skills.mkdir(parents=True)
    for name in ("control-cli", "maintain-verification-skill"):
        (global_skills / name).symlink_to(project / "agents/.agents/davstack/skills" / name)
    requests, issued = [], set()

    class Provider(http.server.BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            text = json.dumps(body["messages"])
            parent = re.search(r"ROOT_AGENT_TOOLS:([a-z-]+)", text)
            child = re.search(r"CHILD_AGENT_TOOLS:([a-z-]+)", text)
            case = (parent or child).group(1)
            requests.append({"case": case, "child": parent is None, "request": body})
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()

            def chunk(delta, finish=None):
                payload = {"choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
                self.wfile.write(("data: " + json.dumps(payload) + "\n\n").encode())
                self.wfile.flush()

            if parent and case not in issued:
                issued.add(case)
                arguments = {"message": "CHILD_AGENT_TOOLS:" + case}
                if case != "default":
                    arguments["agent"] = case
                chunk({"tool_calls": [{"index": 0, "id": "spawn-" + case, "type": "function", "function": {
                    "name": "spawn_agent", "arguments": json.dumps(arguments)}}]})
                chunk({}, "tool_calls")
            else:
                chunk({"content": "SCRIPTED_CHILD_DONE" if parent is None else "SCRIPTED_PARENT_DONE"})
                chunk({}, "stop")
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

    provider = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    provider_thread = threading.Thread(target=provider.serve_forever, daemon=True)
    provider_thread.start()
    models = [{"id": name, "upstream_id": name, "protocol": "openai_chat", "reasoning_levels": ["low", "medium", "high", "xhigh"],
               "flags": {"supports_tools": True, "thinking_format": "openai"}}
              for name in ("parent", "gpt-6-luna", "gpt-6.1-sol")]
    credentials = profile / "providers.json"
    credentials.write_text(json.dumps({"providers": [{"id": "openai-codex", "base_url": f"http://127.0.0.1:{provider.server_port}/v1",
        "api_key": "fixture-only", "endpoints": [{"protocol": "openai_chat", "credential_header": "authorization_bearer"}, {"protocol": "openai_responses", "credential_header": "authorization_bearer"}], "models": models}]}))
    credentials.chmod(0o600)
    env = {"PATH": os.environ["PATH"], "HOME": str(root / "home"), "YUKE_APPNAME": "yuke", "TERM": "dumb"}
    for name in ("config", "data", "state", "cache"):
        env["XDG_" + name.upper() + "_HOME"] = str(root / name)
    records, buffer, number = [], b"", 0
    process = None
    results = {}
    errors = (root / "stderr.log").open("w")
    try:
        process = subprocess.Popen([str(binary), "--rpc"], env=env, cwd=root / "work",
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, bufsize=0)

        def rpc(method, params=None):
            nonlocal buffer, number
            number += 1
            request_id = "fixture-" + str(number)
            process.stdin.write((json.dumps({"id": request_id, "method": method, "params": params or {}}) + "\n").encode())
            process.stdin.flush()
            deadline = time.monotonic() + 15
            while True:
                if b"\n" not in buffer:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not select.select([process.stdout], [], [], remaining)[0]:
                        raise TimeoutError(method)
                    data = os.read(process.stdout.fileno(), 65536)
                    assert data, "Native RPC exited before " + method
                    buffer += data
                    continue
                line, buffer = buffer.split(b"\n", 1)
                if not line.strip():
                    continue
                row = json.loads(line)
                records.append(row)
                if row.get("id") == request_id:
                    assert "error" not in row, row
                    return row["result"]

        rpc("initialize")
        cases = {
            "default": ("general", "openai-codex/gpt-6-luna", "medium", "gpt-6-luna"),
            "general": ("general", "openai-codex/gpt-6-luna", "medium", "gpt-6-luna"),
            "dav-agent": ("dav-agent", "openai-codex/parent", "low", "parent"),
            "reviewer": ("reviewer", "openai-codex/gpt-6.1-sol", "xhigh", "gpt-6.1-sol"),
        }
        for case, (role, model, reasoning, upstream) in cases.items():
            parent = rpc("session.create", {"workspace_path": str(root / "work"), "model": "openai-codex/parent", "reasoning": "low", "max_rounds": 4,
                "initial_input": {"type": "content", "content": [{"type": "text", "text": "ROOT_AGENT_TOOLS:" + case}]}})["session"]
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                children = rpc("session.list", {"population": {"type": "children", "parent_id": parent["id"]}})["items"]
                entry = rpc("session.get", {"session_id": parent["id"]})
                if len(children) == 1 and children[0].get("last_run", {}).get("type") == "turn" and entry["activity"]["state"]["type"] == "idle":
                    break
                time.sleep(.05)
            else:
                raise AssertionError(case + " did not complete native child and parent turns")
            child = children[0]["session"]
            assert child["name"] == role, child
            assert child["model"] == model and child["reasoning"] == reasoning, child
            child_history = rpc("session.history", {"session_id": child["id"], "before_message_id": 1000000, "limit": 64})
            (root / (case + "-child-history.json")).write_text(json.dumps(child_history, indent=2))
            config = child_history["configs"][-1]
            assert (config["model"], config["reasoning"]) == (model, reasoning), config
            history = rpc("session.history", {"session_id": parent["id"], "before_message_id": 1000000, "limit": 64})
            (root / (case + "-history.json")).write_text(json.dumps(history, indent=2))
            receipt_text = next(part["state"]["output"] for message in history["messages"] if message["type"] == "assistant"
                                for part in message["content"] if part["type"] == "tool" and part["name"] == "spawn_agent"
                                and part["state"]["type"] == "completed")
            receipt = json.loads(receipt_text.split("Engine model receipt: ", 1)[1])
            assert receipt["model"] == model and receipt["reasoning"] == reasoning, receipt
            assert receipt["parent_model"] == "openai-codex/parent" and receipt["session_id"] == child["id"], receipt
            child_requests = [row["request"] for row in requests if row["case"] == case and row["child"]]
            assert len(child_requests) == 1, child_requests
            assert child_requests[0]["model"] == upstream and child_requests[0]["reasoning_effort"] == reasoning, child_requests
            declared = {tool["function"]["name"] for tool in child_requests[0].get("tools", [])}
            assert "spawn_agent" not in declared and "send_agent_input" not in declared, declared
            catalog = {skill["name"] for skill in entry["skills"]}
            assert {"verify-yuke-profile", "verify-herdr-profile", "verify-neovim-profile", "control-cli", "maintain-verification-skill"} <= catalog, catalog
            results[case] = {"receipt": receipt, "stored_run_config": config, "child_request_model": upstream, "native_project_skill_discovery": True}
            print("PASS", case, model, reasoning, "native receipt, stored config, HTTP route, depth limit, and project catalog", flush=True)
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            process.stdin.close()
            process.stdout.close()
        provider.shutdown()
        provider.server_close()
        provider_thread.join(timeout=5)
        errors.close()
        (root / "requests.json").write_text(json.dumps(requests, indent=2))
        (root / "rpc.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records))
        (root / "result.json").write_text(json.dumps({"cases": results, "native_process_stopped": process is None or process.poll() is not None,
            "real_model_calls": 0, "model_judgment": "NOT_RUN", "different_family_review": "NOT_RUN"}, indent=2))
    print("PASS native routing only. Scripted fixture replies are not model judgment or cross-family proof.")


if __name__ == "__main__":
    main()
