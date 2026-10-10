#!/usr/bin/env python3
"""Check provider completion and optional idle timeout in isolated, detached tmux.

Only a loopback fixture receives requests. No credentials, desktop input, or
clipboard access are needed. Set YUKE to test a different binary.
"""
import argparse
import http.server
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import uuid


def frames(*events):
    return "".join("data: " + (e if isinstance(e, str) else json.dumps(e)) + "\n\n" for e in events).encode()


def response(protocol, tool):
    if protocol == "openai_responses":
        events = [
            {"type": "response.output_item.added", "output_index": 0,
             "item": {"type": "function_call", "call_id": "call_1", "name": "stall_probe"}},
            {"type": "response.function_call_arguments.done", "output_index": 0, "arguments": "{}"},
            {"type": "response.output_item.done", "output_index": 0,
             "item": {"type": "function_call", "arguments": "{}"}},
        ] if tool else [
            {"type": "response.output_item.added", "output_index": 0, "item": {"type": "message"}},
            {"type": "response.content_part.added", "output_index": 0, "content_index": 0,
             "part": {"type": "output_text"}},
            {"type": "response.output_text.delta", "output_index": 0, "delta": "STALL_CHECK_OK"},
            {"type": "response.output_text.done", "output_index": 0},
        ]
        return frames(*events, {"type": "response.completed", "response": {
            "status": "completed", "usage": {"input_tokens": 10, "output_tokens": 5}}})
    if protocol == "openai_chat":
        delta = {"tool_calls": [{"index": 0, "id": "call_1", "type": "function",
                 "function": {"name": "stall_probe", "arguments": "{}"}}]} if tool else {"content": "STALL_CHECK_OK"}
        return frames({"choices": [{"index": 0, "delta": delta,
                                    "finish_reason": "tool_calls" if tool else "stop"}],
                       "usage": {"prompt_tokens": 10, "completion_tokens": 5}}, "[DONE]")
    block = {"type": "tool_use", "id": "call_1", "name": "stall_probe", "input": {}} if tool else {"type": "text", "text": ""}
    delta = {"type": "input_json_delta", "partial_json": "{}"} if tool else {"type": "text_delta", "text": "STALL_CHECK_OK"}
    return frames(
        {"type": "message_start", "message": {"usage": {"input_tokens": 10}}},
        {"type": "content_block_start", "index": 0, "content_block": block},
        {"type": "content_block_delta", "index": 0, "delta": delta},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "tool_use" if tool else "end_turn"}, "usage": {"output_tokens": 5}},
        {"type": "message_stop"},
    )


def check(protocol, binary, tmux_binary, artifacts, silent=False):
    socket = "yuke-provider-stall-" + uuid.uuid4().hex[:10]
    release = threading.Event()
    requests = []
    errors = []

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_POST(self):
            try:
                body = self.rfile.read(int(self.headers["Content-Length"]))
                requests.append(body)
                count = len(requests)
                assert count <= 2, "unexpected retry or extra request"
                if count == 2:
                    assert b"probe-ran" in body, "the next request lost the tool result"
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                if not silent:
                    data = response(protocol, count == 1)
                    self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
                    self.wfile.flush()
                # Withhold the final HTTP chunk even after the protocol terminal.
                release.wait()
                self.close_connection = True
            except Exception as error:
                errors.append(repr(error))

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def tmux(*args, check=True):
        return subprocess.run([tmux_binary, "-L", socket, *args], check=check,
                              capture_output=True, text=True)

    try:
        with tempfile.TemporaryDirectory(prefix="yuke-provider-stall-") as directory:
            root = pathlib.Path(directory)
            profile = root / "config" / "yuke"
            profile.mkdir(parents=True)
            (profile / "index.js").write_text('''import { plugins } from "yuke";
plugins.use({ name: "stall-fixture", apply(ctx) {
  ctx.tools.define({ name: "stall_probe", description: "Return the fixture marker.",
    parameters: { type: "object", properties: {}, additionalProperties: false },
    async execute() { ctx.print("PROBE_EXECUTED"); return "probe-ran"; }
  });
}});
''')
            providers = profile / "providers.json"
            providers.write_text(json.dumps({"providers": [{"id": "stall-fixture",
                "base_url": f"http://127.0.0.1:{server.server_port}/v1",
                "endpoints": [{"protocol": protocol}],
                "models": [{"id": "test", "upstream_id": "test", "protocol": protocol,
                            "limits": {"context_window": 100000, "max_output_tokens": 1000}}]}]}))
            providers.chmod(0o600)
            env = {"XDG_CONFIG_HOME": str(root / "config"), "XDG_DATA_HOME": str(root / "data"),
                   "XDG_STATE_HOME": str(root / "state"), "XDG_CACHE_HOME": str(root / "cache"),
                   "YUKE_APPNAME": "yuke", "TERM": "xterm-256color"}
            command = shlex.join([binary, "-p", "Exercise the loopback fixture.", "--json", "--model", "stall-fixture/test"])
            runner = root / "run.sh"
            runner.write_text("#!/bin/sh\n" + "\n".join(f"export {key}={shlex.quote(value)}" for key, value in env.items())
                + "\nunset HERDR_ENV HERDR_PANE_ID HERDR_SOCKET_PATH\n"
                + f"cd {shlex.quote(str(root))}\n{command} > output 2> stderr\necho $? > exit-code\n")
            runner.chmod(0o700)
            tmux("new-session", "-d", "-x", "100", "-y", "24", "-s", "test", str(runner))
            deadline = time.monotonic() + (140 if silent else 12)
            while not (root / "exit-code").exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            label = protocol + ("-silent" if silent else "-held-open")
            output = (root / "output").read_text() if (root / "output").exists() else ""
            stderr = (root / "stderr").read_text() if (root / "stderr").exists() else ""
            log_path = root / "state" / "yuke" / "yuke.log"
            log = log_path.read_text() if log_path.exists() else ""
            (artifacts / (label + ".log")).write_text(output + "\nSTDERR\n" + stderr + "\nLOG\n" + log)
            assert (root / "exit-code").exists(), f"{label}: did not exit; see {artifacts}"
            code = (root / "exit-code").read_text().strip()
            assert not errors, errors
            assert not release.is_set(), "fixture released HTTP before the client finished"
            result = json.loads(output)
            if silent:
                assert code != "0" and "IdleTimeout" in stderr + log, f"{label}: missing timeout error; see {artifacts}"
                assert result["outcome"] == {"type": "failed", "code": "timeout", "message": "the provider stream timed out"}
                assert len(requests) == 1 and "PROBE_EXECUTED" not in log, "silent request dispatched a tool or retried"
            else:
                assert code == "0", f"{label}: exit {code}; see {artifacts}"
                assert result["text"] == "STALL_CHECK_OK", f"{label}: missing final text"
                assert result["outcome"] == {"type": "turn", "finish": "stop", "rounds": 2}
                assert result["messages"][0]["content"][0]["state"]["output"] == "probe-ran"
                assert len(requests) == 2, f"{label}: tool did not complete the next turn"
                assert log.count("PROBE_EXECUTED") == 1, f"{label}: tool did not run exactly once"
            print("PASS", label)
    finally:
        tmux("kill-server", check=False)
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--silent-timeout", action="store_true", help="also check the installed two-minute idle timeout")
    args = parser.parse_args()
    binary = shutil.which(os.environ.get("YUKE", "yuke"))
    tmux_binary = shutil.which("tmux")
    assert binary and tmux_binary, "yuke and tmux are required"
    artifacts = pathlib.Path(tempfile.mkdtemp(prefix="yuke-provider-stall-artifacts-"))
    print("Artifacts:", artifacts, flush=True)
    for protocol in ("anthropic_messages", "openai_chat", "openai_responses"):
        check(protocol, binary, tmux_binary, artifacts)
    if args.silent_timeout:
        check("openai_responses", binary, tmux_binary, artifacts, silent=True)


if __name__ == "__main__":
    main()
