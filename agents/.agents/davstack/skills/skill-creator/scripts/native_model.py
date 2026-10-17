#!/usr/bin/env python3
"""Bounded Yuke RPC trials with private stores, retained evidence, and sandboxed writes."""
import fcntl
import json
import math
import os
from pathlib import Path
import re
import select
import shutil
import subprocess
import time
import uuid


class NativeRunError(RuntimeError):
    pass


def reserve_run(count=1, *, campaign=False):
    if type(count) is not int or count < 1:
        raise NativeRunError("Reservation count must be a positive integer.")
    if os.environ.get("DAVSTACK_AUTHORING_ALLOW_MODELS") != "1":
        raise NativeRunError("Model runs require explicit authorization and DAVSTACK_AUTHORING_ALLOW_MODELS=1.")
    path = Path(os.environ["DAVSTACK_AUTHORING_BUDGET"]).resolve(strict=True)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        budget = json.loads(path.read_text())
        if not campaign and "campaign_seconds" in budget:
            raise NativeRunError("A campaign budget requires a campaign reservation.")
        if campaign:
            if not (type(budget.get("campaign_seconds")) is int and 5 < budget["campaign_seconds"] <= 900
                    and type(budget["limit"]) is int and 1 <= budget["limit"] <= 12):
                raise NativeRunError("A campaign requires at most 12 sessions and a bounded campaign_seconds budget.")
            if "started_epoch" not in budget:
                if budget["used"] != 0:
                    raise NativeRunError("Cannot attach a campaign to a previously used budget.")
                budget["started_epoch"] = time.time()
                budget["started_monotonic"] = time.monotonic()
            if (type(budget["started_epoch"]) not in (int, float) or not math.isfinite(budget["started_epoch"])
                    or budget["started_epoch"] > time.time()):
                raise NativeRunError("Invalid campaign start time.")
            clock = budget.get("started_monotonic")
            if type(clock) not in (int, float) or not math.isfinite(clock) or clock > time.monotonic():
                raise NativeRunError("Invalid campaign monotonic start time.")
            if time.monotonic() >= clock + budget["campaign_seconds"] - 5:
                raise NativeRunError("Authorized campaign deadline reached.")
        if budget["used"] + count > budget["limit"]:
            raise NativeRunError("Authorized model-run budget exhausted.")
        budget["used"] += count
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(budget, indent=2) + "\n")
        temporary.replace(path)
    return budget["used"]


def run_trial(prompt, model, *, skill_name=None, description=None, skill_content=None,
              admit_skill=False, timeout=60, mode="task", files=None, campaign_slots=None, max_concurrent=2):
    if not model:
        raise NativeRunError("An explicit native provider/model selector is required.")
    if not 0 < timeout <= 60:
        raise NativeRunError("Trial timeout must be between 1 and 60 seconds.")
    if skill_name is not None and (not isinstance(skill_name, str) or len(skill_name) > 64
                                   or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill_name)):
        raise NativeRunError("A skill name must be a lowercase kebab-case component of at most 64 characters.")
    if campaign_slots is not None and (type(campaign_slots) is not int or not 1 <= campaign_slots <= 12):
        raise NativeRunError("A campaign needs between 1 and 12 prepaid session slots.")
    if type(max_concurrent) is not int or not 1 <= max_concurrent <= 12:
        raise NativeRunError("Invalid campaign concurrency limit.")
    binary = shutil.which(os.environ.get("DAVSTACK_AUTHORING_BINARY", "yuke"))
    sandbox = shutil.which("sandbox-exec")
    if not binary or not sandbox:
        raise NativeRunError("This adapter requires Yuke and macOS sandbox-exec; no unsafe fallback.")
    evidence = Path(os.environ["DAVSTACK_AUTHORING_EVIDENCE"]).resolve(strict=True)
    root = evidence / ("run-" + uuid.uuid4().hex)
    try:
        root.mkdir(mode=0o700)
    except OSError as error:
        raise NativeRunError("Cannot create trial evidence: " + str(error)) from error
    records, buffer, sequence = [], b"", 0
    started = time.monotonic()
    deadline = started + timeout
    session = None
    outcomes = {}
    first_tool = None
    trigger_decision = None
    result = {"artifact_dir": str(root), "model_requested": model, "timeout_seconds": timeout,
              "max_rounds": 8, "mode": mode, "status": "INCONCLUSIVE"}
    process = None
    errors = None
    try:
        result["reservation"] = reserve_run(campaign_slots or 1, campaign=campaign_slots is not None)
        if campaign_slots is not None:
            budget = json.loads(Path(os.environ["DAVSTACK_AUTHORING_BUDGET"]).read_text())
            deadline = min(deadline, started + 55, budget["started_monotonic"] + budget["campaign_seconds"] - 5)
            result["reserved_slots"] = campaign_slots
            result["campaign_deadline_epoch"] = budget["started_epoch"] + budget["campaign_seconds"]

        for name in ("home", "work", "data", "state", "cache"):
            (root / name).mkdir()
        if files:
            for name, content in files.items():
                path = root / "work" / name
                if not path.resolve().is_relative_to(root / "work"):
                    raise NativeRunError("Fixture path must stay inside its private workspace.")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
        skill_path = None
        if skill_name:
            skill_path = root / "work/.agents/skills" / skill_name / "SKILL.md"
            if not skill_path.resolve().is_relative_to(root / "work/.agents/skills"):
                raise NativeRunError("Skill path must stay inside its private skills directory.")
            skill_path.parent.mkdir(parents=True)
            if skill_content is None:
                skill_content = f"---\nname: {skill_name}\ndescription: {json.dumps(description)}\n---\n\nThis skill handles: {description}\n"
            skill_path.write_text(skill_content)
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))).resolve()
        env = {"PATH": os.environ["PATH"], "HOME": str(root / "home"), "TERM": "dumb", "SHELL": "/bin/sh",
               "YUKE_APPNAME": os.environ.get("YUKE_APPNAME", "yuke"), "XDG_CONFIG_HOME": str(config_home)}
        for name in ("data", "state", "cache"):
            env["XDG_" + name.upper() + "_HOME"] = str(root / name)
        if campaign_slots is not None:
            skills = root / "work/.agents/skills"
            skills.mkdir(parents=True, exist_ok=True)
            (root / "home/.agents").mkdir()
            (root / "home/.agents/skills").symlink_to(skills, target_is_directory=True)
            guard = {"nonce": uuid.uuid4().hex, "slots": campaign_slots, "workspace": str(root / "work"),
                     "home": str(root / "home"), "deadline_ms": int((time.time() + deadline - time.monotonic()) * 1000),
                     "max_concurrent": max_concurrent}
            env["DAVSTACK_CAMPAIGN"] = json.dumps(guard)
        profile = f'(version 1) (allow default) (deny file-write* (require-not (subpath {json.dumps(str(root))})))'
        profile += ' (deny process-exec (literal "/usr/bin/open") (literal "/usr/bin/osascript") (literal "/usr/bin/pbcopy") (literal "/usr/bin/pbpaste") (literal "/usr/bin/afplay"))'
        (root / "sandbox.sb").write_text(profile)
        errors = (root / "stderr.log").open("w")
        process = subprocess.Popen([sandbox, "-f", str(root / "sandbox.sb"), binary, "--rpc"], cwd=root / "work",
                                   env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, bufsize=0)
        os.set_blocking(process.stdin.fileno(), False)
        def rpc(method, params=None):
            nonlocal buffer, sequence, first_tool, trigger_decision
            sequence += 1
            request_id = "authoring-" + str(sequence)
            pending = memoryview((json.dumps({"id": request_id, "method": method, "params": params or {}}) + "\n").encode())
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Native trial deadline reached.")
                if pending or b"\n" not in buffer:
                    readable, writable, _ = select.select([process.stdout], [process.stdin] if pending else [], [], remaining)
                    if not readable and not writable:
                        raise TimeoutError("Native trial deadline reached.")
                    if writable:
                        try:
                            pending = pending[os.write(process.stdin.fileno(), pending[:65536]):]
                        except BlockingIOError:
                            pass
                    if readable:
                        data = os.read(process.stdout.fileno(), 65536)
                        if not data:
                            raise NativeRunError("Native process exited before " + method)
                        buffer += data
                    if pending or b"\n" not in buffer:
                        continue
                line, buffer = buffer.split(b"\n", 1)
                if not line.strip():
                    continue
                row = json.loads(line)
                records.append(row)
                if row.get("method") == "run.done":
                    outcomes[row["params"]["session_id"]] = row["params"]["outcome"]
                if mode == "trigger" and row.get("method") == "message.part_added" and first_tool is None:
                    event = row["params"]
                    if event["part"]["type"] == "tool":
                        first_tool = event
                if mode == "trigger" and row.get("method") == "tool.state_changed" and first_tool:
                    event = row["params"]
                    if (event["session_id"], event["message_id"], event["part_id"]) == (first_tool["session_id"], first_tool["message_id"], first_tool["part"]["id"]):
                        if event["state"]["type"] == "completed":
                            part = first_tool["part"]
                            selected = False
                            if part["name"] == "read":
                                arguments = json.loads(part["arguments"])
                                read_path = Path(arguments["path"])
                                if not read_path.is_absolute():
                                    read_path = root / "work" / read_path
                                selected = read_path.resolve() == skill_path
                            trigger_decision = {"triggered": selected, "tool": part, "state": event["state"]}
                        elif event["state"]["type"] == "failed":
                            raise NativeRunError("First tool failed; trigger evidence is inconclusive.")
                if row.get("id") == request_id:
                    if "error" in row:
                        raise NativeRunError(str(row["error"]))
                    return row["result"]

        init = rpc("initialize")
        result["engine"] = init["engine"]
        if campaign_slots is not None:
            ack = root / "cache/campaign-ready.json"
            if not ack.is_file() or json.loads(ack.read_text()) != guard:
                raise NativeRunError("Campaign guard bootstrap acknowledgment missing or invalid.")
            result["guard"] = guard
        policy = (f"Work only in this workspace: {root / 'work'}. "
                  "Do not delegate or start background jobs. Do not inspect credentials, user home files, or unrelated chats. "
                  "Do not activate GUI apps, send system-wide input, use clipboard/audio, post externally, push, or deploy. "
                  "Use the available skills normally. Do not claim evidence you did not observe.")
        if campaign_slots is not None:
            policy = policy.replace("Do not delegate or start background jobs.",
                "Delegation through the provided child tools is authorized within the prepaid session quota. "
                "End your turn after dispatch and resume when reports arrive. Do not start background jobs.")
        params = {"workspace_path": str(root / "work"), "model": model,
                  "reasoning": os.environ.get("DAVSTACK_AUTHORING_REASONING", "high"), "max_rounds": 8,
                  "system_prompt": policy,
                  "initial_input": {"type": "content", "content": [{"type": "text", "text": prompt}]}}
        if admit_skill:
            params["initial_input"]["skills"] = [skill_name]
        session = rpc("session.create", params)["session"]
        result["session"] = session
        stable = 0
        while True:
            entry = rpc("session.get", {"session_id": session["id"]})
            if trigger_decision is not None:
                rpc("session.cancel_run", {"session_id": session["id"]})
                break
            if campaign_slots is None:
                if session["id"] in outcomes:
                    break
            else:
                children = rpc("session.list", {"population": {"type": "children", "parent_id": session["id"]}})["items"]
                for child in children:
                    child["terminal_outcome"] = outcomes.get(child["session"]["id"])
                result["children"] = children
                (root / "children.json").write_text(json.dumps(children, indent=2))
                terminal = all(c["activity"]["state"]["type"] == "idle" and c["activity"]["queued"] == 0
                               and (c.get("last_run") or c["terminal_outcome"]) for c in children)
                stable = stable + 1 if terminal and entry["activity"]["state"]["type"] == "idle" and entry["activity"]["queued"] == 0 and session["id"] in outcomes else 0
                if stable >= 2:
                    for child in children:
                        history = rpc("session.history", {"session_id": child["session"]["id"], "before_message_id": 1000000, "limit": 64})
                        (root / (child["session"]["id"] + "-history.json")).write_text(json.dumps(history, indent=2))
                    break
            time.sleep(.05)
        outcome = outcomes.get(session["id"], {"type": "canceled"})
        if trigger_decision is None and (outcome["type"] != "turn" or outcome["finish"] != "stop"):
            raise NativeRunError("Native trial did not complete normally: " + json.dumps(outcome))
        history = rpc("session.history", {"session_id": session["id"], "before_message_id": 1000000, "limit": 64})
        (root / "history.json").write_text(json.dumps(history, indent=2))
        text, triggered, total_tokens = [], False, 0
        for message in history["messages"]:
            if message["type"] != "assistant":
                continue
            tokens = message.get("tokens", {})
            total_tokens += tokens.get("input", 0) + tokens.get("output", 0)
            for part in message["content"]:
                if part["type"] == "text":
                    text.append(part["text"])
                elif part["type"] == "tool" and part["name"] == "read" and part["state"]["type"] == "completed" and skill_path:
                    arguments = json.loads(part["arguments"])
                    read_path = Path(arguments["path"])
                    if not read_path.is_absolute():
                        read_path = root / "work" / read_path
                    triggered |= read_path.resolve() == skill_path
        result.update(status="VERIFIED", outcome=outcome, history_config=history["configs"],
                      trigger_observation=trigger_decision,
                      triggered=trigger_decision["triggered"] if trigger_decision is not None else triggered, text="\n".join(text), total_tokens=total_tokens,
                      duration_ms=round((time.monotonic() - started) * 1000))
        return result
    except (OSError, ValueError, KeyError, TimeoutError, NativeRunError) as error:
        result["error"] = str(error)
        raise NativeRunError(str(error) + "; evidence: " + str(root)) from error
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
        if errors is not None:
            errors.close()
        result["native_process_pid"] = process.pid if process is not None else None
        result["native_process_started"] = process is not None
        result["native_process_stopped"] = process is None or process.poll() is not None
        (root / "rpc.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records))
        (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")


def complete_text(prompt, model):
    return run_trial(prompt, model, mode="description-proposal")["text"]
