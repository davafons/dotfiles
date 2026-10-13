#!/usr/bin/env python3
"""Probe native custom-agent discovery without model turns or user-session access."""
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import tempfile
import time


SOURCE = Path(__file__).resolve().parents[2] / "agents/.agents/davstack/skills"
AGENTS = {"comment-sicko": "comment-sicko", "dav-agent": "dav-mode"}


def exchange(argv, env, cwd, artifact, requests, reply_id):
    records = []
    buffer = b""
    with artifact.with_suffix(".stderr").open("w") as errors:
        process = subprocess.Popen(
            argv, env=env, cwd=cwd, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=errors, bufsize=0,
        )
        try:
            for request in requests:
                process.stdin.write((json.dumps(request) + "\n").encode())
                process.stdin.flush()
                if "id" not in request and "request_id" not in request:
                    continue
                expected = request.get("id", request.get("request_id"))
                deadline = time.monotonic() + 20
                while True:
                    if b"\n" not in buffer:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError(f"No native response for {expected}")
                        ready, _, _ = select.select([process.stdout], [], [], remaining)
                        if not ready:
                            raise TimeoutError(f"No native response for {expected}")
                        data = os.read(process.stdout.fileno(), 65536)
                        if not data:
                            raise RuntimeError(f"Native process exited before {expected}")
                        buffer += data
                        continue
                    line, buffer = buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    response = json.loads(line)
                    records.append(response)
                    if reply_id(response) == expected:
                        break
            return records
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            process.stdin.close()
            process.stdout.close()
            artifact.write_text("".join(json.dumps(row) + "\n" for row in records))


def claude_catalog(binary, home, work, root, bare=False):
    env = {
        "PATH": os.environ["PATH"], "HOME": str(home), "TERM": "dumb",
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        "ANTHROPIC_API_KEY": "local-diagnostic-not-a-credential",
        "ANTHROPIC_BASE_URL": "http://127.0.0.1:9",
        "DISABLE_TELEMETRY": "1", "DISABLE_ERROR_REPORTING": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }
    argv = [binary, "--print", "--input-format", "stream-json",
            "--output-format", "stream-json", "--verbose", "--strict-mcp-config",
            "--mcp-config", '{"mcpServers":{}}', "--setting-sources", "user"]
    if bare:
        argv.append("--bare")
    records = exchange(
        argv, env, work, root / ("claude-bare.jsonl" if bare else "claude-directory.jsonl"),
        [{"type": "control_request", "request_id": "catalog",
          "request": {"subtype": "initialize"}}],
        lambda row: row.get("response", {}).get("request_id"),
    )
    response = next(row["response"] for row in records if row.get("type") == "control_response")
    assert response["subtype"] == "success", response
    return {agent["name"] for agent in response["response"]["agents"]}


def codex_diagnostics(binary, home, work, root):
    config = home / ".codex/config.toml"
    config.write_text(
        'model="local-diagnostics"\nmodel_provider="offline"\n'
        '[model_providers.offline]\nname="Offline diagnostics"\n'
        'base_url="http://127.0.0.1:9/v1"\nwire_api="responses"\n'
        'requires_openai_auth=false\n[features]\nmulti_agent=true\n'
    )
    env = {"PATH": os.environ["PATH"], "HOME": str(home),
           "CODEX_HOME": str(home / ".codex"), "TERM": "dumb"}
    records = exchange(
        [binary, "app-server", "--stdio"], env, work, root / "codex-native.jsonl",
        [
            {"id": 1, "method": "initialize", "params": {
                "clientInfo": {"name": "davstack-local-diagnostics", "version": "1"},
                "capabilities": {"experimentalApi": True}}},
            {"method": "initialized"},
            {"id": 2, "method": "config/read", "params": {
                "cwd": str(work), "includeLayers": True}},
            {"id": 3, "method": "thread/start", "params": {
                "cwd": str(work), "ephemeral": True, "approvalPolicy": "never",
                "sandbox": "read-only", "model": "local-diagnostics",
                "modelProvider": "offline"}},
        ], lambda row: row.get("id"),
    )
    replies = {row["id"]: row for row in records if "id" in row}
    assert all("result" in replies[key] for key in (1, 2, 3)), replies
    assert replies[2]["result"]["config"]["model_provider"] == "offline"
    thread = replies[3]["result"]
    assert thread["sandbox"] == {"type": "readOnly", "networkAccess": False}, thread
    assert thread["thread"]["turns"] == [], thread
    assert thread["thread"]["ephemeral"] is True, thread
    return {"offline_config": "PASS", "empty_read_only_thread": "PASS",
            "custom_agent_catalog": "NOT_EXPOSED_BY_THESE_DIAGNOSTICS",
            "active_agent_execution": "NOT_RUN"}


def main():
    binaries = {name: shutil.which(name) for name in ("claude", "codex")}
    assert all(binaries.values()), "Install both native CLIs before running this optional check"
    root = Path(tempfile.mkdtemp(prefix="davstack-agent-discovery-")).resolve()
    root.chmod(0o700)
    print(f"Artifacts: {root}", flush=True)
    home, work = root / "home", root / "work"
    work.mkdir()
    for harness, filename in (("claude", "claude.md"), ("codex", "codex.toml")):
        directory = home / f".{harness}" / "agents"
        directory.mkdir(parents=True)
        for name, package in AGENTS.items():
            (directory / f"{name}.{filename.rsplit('.', 1)[1]}").symlink_to(
                SOURCE / package / "agents" / filename)
    (home / ".claude/settings.json").write_text("{}")
    bare = claude_catalog(binaries["claude"], home, work, root, bare=True)
    assert not set(AGENTS) & bare, "Bare mode unexpectedly discovered user agents"
    catalog = claude_catalog(binaries["claude"], home, work, root)
    assert set(AGENTS) <= catalog, "The native directory loader missed custom agents"
    report = {
        "claude": {"custom_agent_catalog": "PASS", "agents": sorted(set(AGENTS) & catalog),
                   "bare_mode_excludes_user_agents": "PASS", "active_agent_execution": "NOT_RUN"},
        "codex": codex_diagnostics(binaries["codex"], home, work, root),
        "model_turns": 0,
    }
    (root / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
