#!/usr/bin/env python3
"""Exercise native child routing and model receipts with a scripted localhost provider over `yuke --rpc`."""
import argparse
import http.server
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

APP = "yuke-rust"
WAIT = 20
SKILLS = {"verify-yuke-profile", "verify-herdr-profile", "verify-neovim-profile", "control-cli", "maintain-verification-skill"}
CASES = {
    # case: (role, model, reasoning effort, upstream model)
    "default": ("general", "openai-codex/gpt-6-luna", "medium", "gpt-6-luna"),
    "general": ("general", "openai-codex/gpt-6-luna", "medium", "gpt-6-luna"),
    "dav-agent": ("dav-agent", "openai-codex/parent", "low", "parent"),
    "reviewer": ("reviewer", "openai-codex/gpt-6.1-sol", "xhigh", "gpt-6.1-sol"),
}


class Provider:
    """A scripted OpenAI chat endpoint. Each root asks for one child, and every other request ends its turn."""

    def __init__(self):
        self.requests, self.issued, self.errors = [], set(), []
        provider = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *unused):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                text = json.dumps(body.get("messages"))
                parent = re.search(r"ROOT_AGENT_TOOLS:([a-z-]+)", text)
                child = re.search(r"CHILD_AGENT_TOOLS:([a-z-]+)", text)
                if parent is None and child is None:
                    provider.errors.append(text[-500:])
                    self.send_error(500)
                    return
                case = (parent or child).group(1)
                provider.requests.append({"case": case, "child": parent is None, "request": body})
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()

                def chunk(delta, finish=None):
                    payload = {"id": "fixture", "object": "chat.completion.chunk", "model": body.get("model"),
                               "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
                    self.wfile.write(("data: " + json.dumps(payload) + "\n\n").encode())

                if parent and case not in provider.issued:
                    provider.issued.add(case)
                    arguments = {"message": "CHILD_AGENT_TOOLS:" + case, "description": "fixture " + case}
                    if case != "default":
                        arguments["agent"] = case
                    chunk({"role": "assistant", "tool_calls": [{"index": 0, "id": "spawn-" + case, "type": "function",
                                                                "function": {"name": "spawn_agent", "arguments": json.dumps(arguments)}}]})
                    chunk({}, "tool_calls")
                else:
                    chunk({"role": "assistant", "content": "SCRIPTED_CHILD_DONE" if parent is None else "SCRIPTED_PARENT_DONE"})
                    chunk({}, "stop")
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def of(self, case, child):
        return [row["request"] for row in self.requests if row["case"] == case and row["child"] == child]


class Client:
    """A JSON-RPC 2.0 client of `yuke --rpc`. Notifications are kept in order for the record."""

    def __init__(self, binary, env, cwd, errors):
        self.process = subprocess.Popen([str(binary), "--rpc"], env=env, cwd=cwd, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=errors, text=True)
        self.lines, self.records, self.replies, self.next_id = queue.Queue(), [], {}, 0
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        for line in self.process.stdout:
            if line.strip():
                self.lines.put(json.loads(line))
        self.lines.put(None)

    def call(self, method, params=None):
        self.next_id += 1
        request = self.next_id
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request, "method": method, "params": params or {}}) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + WAIT
        while request not in self.replies:
            try:
                message = self.lines.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                raise TimeoutError(method) from None
            assert message is not None, "native RPC exited before " + method
            self.records.append(message)
            if "id" in message and "method" not in message:
                self.replies[message["id"]] = message
        reply = self.replies.pop(request)
        assert "error" not in reply, f"{method}: {reply['error']}"
        return reply["result"]

    def stop(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process.stdin.close()
        self.process.stdout.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=Path(shutil.which("yuke") or "yuke"))
    parser.add_argument("--plugin", type=Path, default=Path(__file__).resolve().parents[1] / ".config/yuke-rust/plugins/agent-tools")
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    source = args.plugin.resolve(strict=True)
    project = Path(__file__).resolve().parents[2]
    root = Path(tempfile.mkdtemp(prefix="yuke-agent-tools-")).resolve()
    root.chmod(0o700)
    print("Artifacts:", root, flush=True)
    for name in ("home", "work", "config/" + APP, "data/" + APP, "state", "cache"):
        (root / name).mkdir(parents=True)
    profile = root / "config" / APP
    shutil.copytree(source, profile / "agent-tools", ignore=shutil.ignore_patterns("upstream-tests"))
    (profile / "config.json").write_text('{"plugins":["./agent-tools"]}')
    local_skills = root / "work/.agents/skills"
    local_skills.mkdir(parents=True)
    for name in ("verify-yuke-profile", "verify-herdr-profile", "verify-neovim-profile"):
        (local_skills / name).symlink_to(project / ".agents/skills" / name)
    global_skills = root / "home/.agents/skills"
    global_skills.mkdir(parents=True)
    for name in ("control-cli", "maintain-verification-skill"):
        (global_skills / name).symlink_to(project / "agents/.agents/davstack/skills" / name)

    provider = Provider()
    models = [{"id": name, "upstreamId": name, "protocol": "openai_chat", "reasoningLevels": ["low", "medium", "high", "xhigh"], "flags": {"thinkingFormat": "openai"},
               "limits": {"contextWindow": 100000, "maxOutputTokens": 4000}}
              for name in ("parent", "gpt-6-luna", "gpt-6.1-sol")]
    # openai-codex is a login provider. Its endpoint points at the fixture, and auth.json holds a fixture login.
    (profile / "providers.json").write_text(json.dumps({"providers": [{
        "id": "openai-codex", "baseUrl": f"http://127.0.0.1:{provider.server.server_port}/v1",
        "endpoints": [{"protocol": "openai_chat", "credentialHeader": "authorization_bearer"}, {"protocol": "openai_responses", "credentialHeader": "authorization_bearer"}], "models": models}]}))
    auth = root / "data" / APP / "auth.json"
    expires = int((time.time() + 86400) * 1000)
    auth.write_text(json.dumps({"openai-codex": {"access_token": "fixture-only", "refresh_token": "fixture-only",
                                                 "expires_at": expires, "account_id": "fixture"}}))
    auth.chmod(0o600)
    env = {"PATH": os.environ["PATH"], "HOME": str(root / "home"), "YUKE_APPNAME": APP, "TERM": "dumb"}
    for name in ("config", "data", "state", "cache"):
        env["XDG_" + name.upper() + "_HOME"] = str(root / name)

    results, sessions = {}, {}
    errors = (root / "stderr.log").open("w")
    client = None
    try:
        client = Client(binary, env, root / "work", errors)
        client.call("initialize", {"protocolVersion": 1, "clientInfo": {"name": "check-agent-tools", "version": "1"}})
        for case in CASES:
            settings = {"reasoning": {"effort": "low"}, "toolChoice": "auto"}
            parent = client.call("session/new", {"model": {"provider": "openai-codex", "model": "parent"},
                                                 "settings": settings, "folder": str(root / "work")})["sessionId"]
            client.call("session/input", {"sessionId": parent, "content": [{"kind": "userText", "text": "ROOT_AGENT_TOOLS:" + case}]})
            deadline = time.monotonic() + WAIT
            while time.monotonic() < deadline:
                assert not provider.errors, provider.errors
                children = client.call("session/list", {"parent": parent})["sessions"]
                row = client.call("session/get", {"sessionId": parent})
                row = row.get("session", row)
                # The parent reads the spawn receipt, then the background report, and goes idle.
                reported = any("SCRIPTED_CHILD_DONE" in json.dumps(body.get("messages")) for body in provider.of(case, False))
                if len(children) == 1 and children[0]["state"] != "running" and reported and row["state"] == "idle":
                    break
                time.sleep(0.05)
            else:
                raise AssertionError(case + " did not complete native child and parent turns")
            child = children[0]
            role, model, reasoning, upstream = CASES[case]
            provider_id, model_id = model.split("/")
            assert child["parent"] == parent, child
            assert child["model"] == {"provider": provider_id, "model": model_id}, child
            sessions[case] = (parent, child["sessionId"])

            receipt_text = next(message["content"] for body in provider.of(case, False) for message in body["messages"]
                                if message.get("role") == "tool" and "Engine model receipt: " in json.dumps(message.get("content")))
            if not isinstance(receipt_text, str):
                receipt_text = "".join(part.get("text", "") for part in receipt_text)
            receipt = json.loads(receipt_text.split("Engine model receipt: ", 1)[1].splitlines()[0])
            assert receipt["agent"] == role and receipt["session_id"] == child["sessionId"], receipt
            assert receipt["model"] == {"provider": provider_id, "model": model_id}, receipt
            assert receipt["reasoning"].get("effort") == reasoning, receipt
            assert receipt["parent_model"] == {"provider": "openai-codex", "model": "parent"}, receipt
            stored_role = json.loads(next((root / "data" / APP / "plugins/agent-tools").rglob(child["sessionId"] + ".json")).read_text())
            assert stored_role == role, stored_role

            child_requests = provider.of(case, True)
            assert len(child_requests) == 1, child_requests
            assert child_requests[0]["model"] == upstream, child_requests[0]["model"]
            assert child_requests[0].get("reasoning_effort") == reasoning, {key: value for key, value in child_requests[0].items() if key != "messages"}
            declared = {tool["function"]["name"] for tool in child_requests[0].get("tools", [])}
            assert "spawn_agent" not in declared and "send_agent_input" not in declared, declared
            prompt = json.dumps(provider.of(case, False)[0]["messages"])
            catalog = {name for name in SKILLS if f"<name>{name}</name>" in prompt}
            assert catalog == SKILLS, SKILLS - catalog
            results[case] = {"receipt": receipt, "child_request_model": upstream, "stored_role": stored_role,
                             "native_project_and_global_skill_discovery": True}
            print("PASS", case, model, reasoning, "native receipt, role, HTTP route, depth limit, and skill catalog", flush=True)
    finally:
        if client is not None:
            client.stop()
        provider.server.shutdown()
        provider.server.server_close()
        provider.thread.join(timeout=5)
        errors.close()
        (root / "requests.json").write_text(json.dumps(provider.requests, indent=2))
        if client is not None:
            (root / "rpc.jsonl").write_text("".join(json.dumps(row) + "\n" for row in client.records))

    # The stored settings of each child, read after the native process stopped.
    for case, (_parent, child) in sessions.items():
        _role, model, reasoning, _upstream = CASES[case]
        log = root / "data" / APP / "sessions" / uuid.UUID(child).hex / "events.jsonl"
        settings = [event for event in map(json.loads, log.read_text().splitlines()) if event["kind"] == "settings"][-1]
        stored = (f"{settings['model']['provider']}/{settings['model']['model']}", settings["settings"]["reasoning"].get("effort"))
        assert stored == (model, reasoning), (case, settings)
        results[case]["stored_run_config"] = settings
    print("PASS stored child settings for", ", ".join(sessions), flush=True)
    (root / "result.json").write_text(json.dumps({"cases": results, "native_process_stopped": True, "real_model_calls": 0,
                                                  "model_judgment": "NOT_RUN", "different_family_review": "NOT_RUN"}, indent=2))
    print("PASS native routing only. Scripted fixture replies are not model judgment or cross-family proof.")


if __name__ == "__main__":
    main()
