"""Exercise native trigger observations and budget refusal without real model calls."""
import http.server
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "agents/.agents/davstack/skills/skill-creator/scripts/native_model.py"
spec = importlib.util.spec_from_file_location("authoring_native", SCRIPT)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


@unittest.skipUnless(shutil.which("yuke") and shutil.which("sandbox-exec"), "Native Yuke/macOS runtime unavailable")
class NativeAuthoring(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="authoring-behavior-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        config = self.root / "config/yuke"
        config.mkdir(parents=True)
        (config / "config.json").write_text('{"plugins":[]}')
        self.requests = []
        test = self

        class Provider(http.server.BaseHTTPRequestHandler):
            def log_message(self, *unused):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                test.requests.append(body)
                if "FAIL_PROVIDER" in json.dumps(body["messages"]):
                    failed = json.dumps({"error": {"message": "fixture rejected this request"}}).encode()
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(failed)))
                    self.end_headers()
                    self.wfile.write(failed)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                text = json.dumps(body["messages"])
                if hasattr(test, "respond"):
                    delta, finish = test.respond(body)
                elif "OBSERVE_READ" in text:
                    path = re.search(r"(/[^\s\"<>]+/SKILL\.md)", text).group(1)
                    delta = {"tool_calls": [{"index": 0, "id": "fixture-read", "type": "function", "function": {
                        "name": "read", "arguments": json.dumps({"path": path})}}]}
                    finish = "tool_calls"
                else:
                    delta, finish = {"content": "A conceptual answer without tools."}, "stop"
                self.wfile.write(("data: " + json.dumps({"choices": [{"index": 0, "delta": delta, "finish_reason": None}]}) + "\n\n").encode())
                self.wfile.write(("data: " + json.dumps({"choices": [{"index": 0, "delta": {}, "finish_reason": finish}]}) + "\n\ndata: [DONE]\n\n").encode())
                self.wfile.flush()

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Provider)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        provider = config / "providers.json"
        provider.write_text(json.dumps({"providers": [{"id": "fixture", "base_url": f"http://127.0.0.1:{self.server.server_port}/v1",
            "api_key": "fixture-only", "endpoints": [{"protocol": "openai_chat", "credential_header": "authorization_bearer"}],
            "models": [{"id": "model", "upstream_id": "model", "reasoning_levels": ["high"], "flags": {"supports_tools": True, "thinking_format": "openai"}}]}]}))
        provider.chmod(0o600)
        self.budget = self.root / "budget.json"
        self.budget.write_text('{"limit":2,"used":0}')
        env = patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root / "config"), "DAVSTACK_AUTHORING_ALLOW_MODELS": "1",
            "DAVSTACK_AUTHORING_BUDGET": str(self.budget), "DAVSTACK_AUTHORING_EVIDENCE": str(self.root)})
        env.start()
        self.addCleanup(env.stop)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def test_actual_completed_read_is_observed_then_owned_trial_stops(self):
        result = native.run_trial("OBSERVE_READ", "fixture/model", skill_name="fixture-reader", description="Use for fixture selection.", mode="trigger", timeout=15)
        self.assertIs(result["triggered"], True)
        self.assertEqual(result["trigger_observation"]["tool"]["name"], "read")
        self.assertEqual(result["trigger_observation"]["state"]["type"], "completed")
        self.assertEqual(result["session"]["max_rounds"], 8)
        self.assertIs(result["native_process_stopped"], True)
        self.assertEqual(json.loads(self.budget.read_text())["used"], 1)
        self.assertTrue((Path(result["artifact_dir"]) / "history.json").exists())

    def test_normal_nontrigger_and_exhausted_budget_are_distinct(self):
        result = native.run_trial("Explain the concept only", "fixture/model", skill_name="fixture-reader", description="Use for fixture selection.", mode="trigger", timeout=15)
        self.assertIs(result["triggered"], False)
        self.assertEqual(result["text"], "A conceptual answer without tools.")
        self.assertEqual(result["status"], "VERIFIED")
        self.budget.write_text('{"limit":2,"used":2}')
        before = len(self.requests)
        with self.assertRaisesRegex(native.NativeRunError, "budget exhausted"):
            native.run_trial("Explain again", "fixture/model", timeout=15)
        self.assertEqual(len(self.requests), before)
        self.assertEqual(json.loads(self.budget.read_text()), {"limit": 2, "used": 2})

    def test_provider_failure_is_inconclusive_not_a_correct_negative(self):
        with self.assertRaises(native.NativeRunError):
            native.run_trial("FAIL_PROVIDER", "fixture/model", mode="trigger", timeout=5)
        evidence = next(self.root.glob("run-*/result.json"))
        result = json.loads(evidence.read_text())
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertIn("error", result)
        self.assertIs(result["native_process_stopped"], True)
        self.assertEqual(json.loads(self.budget.read_text())["used"], 1)


    def enable_campaign(self):
        profile = self.root / "config/yuke"
        shutil.copytree(ROOT / "yuke/.config/yuke/plugins/agent-tools", profile / "agent-tools")
        (profile / "config.json").write_text('{"plugins":["./agent-tools"]}')
        path = profile / "providers.json"
        config = json.loads(path.read_text())
        config["providers"].append({"id": "openai-codex", "base_url": f"http://127.0.0.1:{self.server.server_port}/v1",
            "api_key": "fixture-only", "endpoints": [{"protocol": "openai_chat", "credential_header": "authorization_bearer"},
                {"protocol": "openai_responses", "credential_header": "authorization_bearer"}],
            "models": [{"id": name, "upstream_id": name, "protocol": "openai_chat", "reasoning_levels": ["medium", "high", "xhigh"],
                "flags": {"supports_tools": True, "thinking_format": "openai"}} for name in ("gpt-6-luna", "gpt-6.1-sol")]})
        path.write_text(json.dumps(config))
        self.budget.write_text('{"limit":12,"used":0,"campaign_seconds":900}')

    def tool_delta(self, name, arguments, index=0):
        return {"index": index, "id": name + "-" + str(len(self.requests)) + "-" + str(index), "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)}}

    def test_campaign_requires_bootstrap_before_any_provider_request(self):
        self.budget.write_text('{"limit":2,"used":0,"campaign_seconds":900}')
        with self.assertRaisesRegex(native.NativeRunError, "guard"):
            native.run_trial("Never sent", "fixture/model", campaign_slots=2, timeout=5)
        self.assertEqual(self.requests, [])
        self.assertEqual(json.loads(self.budget.read_text())["used"], 2)

    def test_campaign_caps_actual_child_requests_and_records_terminal_history(self):
        self.enable_campaign()
        def respond(body):
            calls = [r for r in self.requests if r["model"] == body["model"]]
            if body["model"] == "model":
                if len(calls) == 1:
                    return {"tool_calls": [self.tool_delta("spawn_agent", {"message": "Read nonce.txt until finished."})]}, "tool_calls"
                return {"content": "Parent finished."}, "stop"
            return {"tool_calls": [self.tool_delta("read", {"path": "nonce.txt"})]}, "tool_calls"
        self.respond = respond
        result = native.run_trial("Coordinate the worker.", "fixture/model", campaign_slots=2, timeout=15, files={"nonce.txt": "private"})
        child_calls = [r for r in self.requests if r["model"] == "gpt-6-luna"]
        self.assertEqual(len(child_calls), 8)
        self.assertEqual(len(result["children"]), 1)
        child = result["children"][0]
        self.assertEqual(child["session"]["max_rounds"], 8)
        self.assertEqual(child["last_run"]["type"], "failed")
        self.assertEqual(child["last_run"]["code"], "max_rounds")
        history = json.loads((Path(result["artifact_dir"]) / (child["session"]["id"] + "-history.json")).read_text())
        self.assertEqual(len([m for m in history["messages"] if m["type"] == "assistant"]), 8)
        self.assertEqual(json.loads(self.budget.read_text())["used"], 2)
        self.assertIs(result["native_process_stopped"], True)

    def test_campaign_rejects_unfunded_child_before_creation(self):
        self.enable_campaign()
        def respond(body):
            calls = [r for r in self.requests if r["model"] == body["model"]]
            if body["model"] == "model" and len(calls) == 1:
                return {"tool_calls": [self.tool_delta("spawn_agent", {"message": "Report only."}, i) for i in range(2)]}, "tool_calls"
            return {"content": "Done."}, "stop"
        self.respond = respond
        result = native.run_trial("Coordinate both workers.", "fixture/model", campaign_slots=2, timeout=10)
        self.assertEqual(len(result["children"]), 1)
        self.assertEqual(len([r for r in self.requests if r["model"] == "gpt-6-luna"]), 1)
        history = json.loads((Path(result["artifact_dir"]) / "history.json").read_text())
        failures = [p["state"] for m in history["messages"] if m["type"] == "assistant" for p in m["content"]
                    if p["type"] == "tool" and p["name"] == "spawn_agent" and p["state"]["type"] == "error"]
        self.assertEqual(len(failures), 1)
        self.assertIn("quota", json.dumps(failures).lower())

    def test_campaign_round_count_survives_parent_resumption(self):
        self.enable_campaign()
        release = threading.Event()
        def respond(body):
            calls = [r for r in self.requests if r["model"] == body["model"]]
            if body["model"] != "model":
                release.wait(3)
                time.sleep(.1)
                return {"content": "Child finished."}, "stop"
            if len(calls) == 1:
                return {"tool_calls": [self.tool_delta("spawn_agent", {"message": "Report when finished."})]}, "tool_calls"
            if len(calls) < 8:
                return {"tool_calls": [self.tool_delta("read", {"path": "nonce.txt"})]}, "tool_calls"
            release.set()
            return {"content": "Parent stopped."}, "stop"
        self.respond = respond
        with self.assertRaises(native.NativeRunError):
            native.run_trial("Coordinate the worker.", "fixture/model", campaign_slots=2, timeout=10, files={"nonce.txt": "private"})
        self.assertEqual(len([r for r in self.requests if r["model"] == "model"]), 8)
        result = json.loads(next(self.root.glob("run-*/result.json")).read_text())
        self.assertIn('"code": "runtime"', result["error"])
        self.assertIs(result["native_process_stopped"], True)

    def test_campaign_drains_queued_children_before_returning(self):
        self.enable_campaign()
        def respond(body):
            calls = [r for r in self.requests if r["model"] == body["model"]]
            if body["model"] == "model" and len(calls) == 1:
                return {"tool_calls": [self.tool_delta("spawn_agent", {"message": "Report only."}, i) for i in range(2)]}, "tool_calls"
            if body["model"] != "model":
                time.sleep(.15)
            return {"content": "Done."}, "stop"
        self.respond = respond
        result = native.run_trial("Coordinate both workers.", "fixture/model", campaign_slots=3, max_concurrent=1, timeout=10)
        self.assertEqual(len(result["children"]), 2)
        self.assertTrue(all(c["last_run"]["type"] == "turn" for c in result["children"]))
        self.assertEqual(len([r for r in self.requests if r["model"] == "gpt-6-luna"]), 2)
        history = json.loads((Path(result["artifact_dir"]) / "history.json").read_text())
        outputs = [p["state"].get("output", "") for m in history["messages"] if m["type"] == "assistant"
                   for p in m["content"] if p["type"] == "tool" and p["name"] == "spawn_agent"]
        self.assertTrue(any(text.startswith("Queued ") for text in outputs), outputs)

    def test_campaign_stop_is_terminal_without_inventing_a_child_report(self):
        self.enable_campaign()
        def respond(body):
            if body["model"] != "model":
                return {"tool_calls": [self.tool_delta("read", {"path": "nonce.txt"})]}, "tool_calls"
            calls = [r for r in self.requests if r["model"] == "model"]
            if len(calls) == 1:
                return {"tool_calls": [self.tool_delta("spawn_agent", {"message": "Read nonce.txt repeatedly."})]}, "tool_calls"
            if len(calls) == 2:
                child = re.search(r"general-[a-f0-9]{8}", json.dumps(body)).group(0)
                return {"tool_calls": [self.tool_delta("stop", {"id": child})]}, "tool_calls"
            return {"content": "Worker stopped; its slice has no report."}, "stop"
        self.respond = respond
        result = native.run_trial("Start then cancel the worker.", "fixture/model", campaign_slots=2, timeout=10, files={"nonce.txt": "private"})
        self.assertEqual(len(result["children"]), 1)
        child = result["children"][0]
        self.assertEqual(child["terminal_outcome"]["type"], "canceled")
        self.assertLessEqual(len([r for r in self.requests if r["model"] == "gpt-6-luna"]), 8)
        self.assertIn("no report", result["text"])

    def test_campaign_failed_creation_keeps_its_slot_consumed(self):
        self.enable_campaign()
        p = self.root / "config/yuke/providers.json"
        config = json.loads(p.read_text())
        config["providers"][1]["models"][1]["reasoning_levels"] = ["high"]
        p.write_text(json.dumps(config))
        def respond(body):
            if len(self.requests) == 1:
                return {"tool_calls": [self.tool_delta("spawn_agent", {"agent": role, "message": "Report only."}, i)
                        for i, role in enumerate(("reviewer", "general"))]}, "tool_calls"
            return {"content": "Done."}, "stop"
        self.respond = respond
        result = native.run_trial("Coordinate both workers.", "fixture/model", campaign_slots=2, timeout=10)
        self.assertEqual(result["children"], [])
        self.assertFalse(any(r["model"] != "model" for r in self.requests))
        self.assertEqual(json.loads(self.budget.read_text())["used"], 2)

    def test_campaign_deadline_stops_an_inflight_child_and_reaps_the_process(self):
        self.enable_campaign()
        started, release = threading.Event(), threading.Event()
        def respond(body):
            if body["model"] != "model":
                started.set()
                release.wait(5)
                return {"content": "Too late."}, "stop"
            if len([r for r in self.requests if r["model"] == "model"]) == 1:
                return {"tool_calls": [self.tool_delta("spawn_agent", {"message": "Wait for the result."})]}, "tool_calls"
            return {"content": "Waiting."}, "stop"
        self.respond = respond
        begin = time.monotonic()
        try:
            with self.assertRaisesRegex(native.NativeRunError, "deadline"):
                native.run_trial("Coordinate the worker.", "fixture/model", campaign_slots=2, timeout=2)
            self.assertTrue(started.is_set())
            self.assertLess(time.monotonic() - begin, 4)
            result = json.loads(next(self.root.glob("run-*/result.json")).read_text())
            with self.assertRaises(ProcessLookupError):
                os.kill(result["native_process_pid"], 0)
            self.assertEqual(json.loads(self.budget.read_text())["used"], 2)
        finally:
            release.set()

    def test_global_campaign_deadline_also_stops_an_active_root(self):
        self.enable_campaign()
        self.budget.write_text('{"limit":12,"used":0,"campaign_seconds":6}')
        self.respond = lambda body: (time.sleep(2) or {"content": "Too late."}, "stop")
        begin = time.monotonic()
        with self.assertRaisesRegex(native.NativeRunError, "deadline"):
            native.run_trial("Wait for the result.", "fixture/model", campaign_slots=1, timeout=20)
        self.assertLess(time.monotonic() - begin, 3)
        result = json.loads(next(self.root.glob("run-*/result.json")).read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(result["native_process_pid"], 0)
        self.assertEqual(json.loads(self.budget.read_text())["used"], 1)

    def test_campaign_judge_uses_the_approved_existing_family_selector(self):
        self.enable_campaign()
        p = self.root / "config/yuke/providers.json"
        config = json.loads(p.read_text())
        config["providers"].append({"id": "xai-grok", "base_url": f"http://127.0.0.1:{self.server.server_port}/v1",
            "api_key": "fixture-only", "endpoints": [{"protocol": "openai_chat", "credential_header": "authorization_bearer"},
                {"protocol": "openai_responses", "credential_header": "authorization_bearer"}],
            "models": [{"id": "grok-4.7", "upstream_id": "grok-4.7", "protocol": "openai_chat", "reasoning_levels": ["medium", "high"],
                "flags": {"supports_tools": True, "thinking_format": "openai"}}]})
        p.write_text(json.dumps(config))
        self.respond = lambda body: ({"content": "Judgment complete."}, "stop")
        result = native.run_trial("Judge artifacts A and B only.", "xai-grok/grok-4.7", campaign_slots=1, timeout=10)
        self.assertEqual((result["session"]["model"], result["session"]["max_rounds"]), ("xai-grok/grok-4.7", 8))
        self.assertEqual(result["children"], [])
        self.assertEqual(len([r for r in self.requests if r["model"] == "grok-4.7"]), 1)

    def test_campaign_refuses_tools_outside_the_private_workspace(self):
        self.enable_campaign()
        protected = self.root / "protected.txt"
        protected.write_text("unchanged")
        def respond(body):
            if len(self.requests) == 1:
                return {"tool_calls": [self.tool_delta("write", {"path": str(protected), "content": "modified"})]}, "tool_calls"
            return {"content": "Done."}, "stop"
        self.respond = respond
        native.run_trial("Write the requested artifact.", "fixture/model", campaign_slots=1, timeout=10)
        self.assertEqual(protected.read_text(), "unchanged")
        self.assertTrue(all(t["function"]["name"] in {"read", "write", "edit", "spawn_agent", "send_agent_input", "stop"}
                            for r in self.requests for t in r.get("tools", [])))


class NativeBoundaries(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="authoring-boundaries-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.budget = self.root / "budget.json"
        self.budget.write_text('{"limit":20,"used":0}')
        env = patch.dict(os.environ, {
            "DAVSTACK_AUTHORING_ALLOW_MODELS": "1",
            "DAVSTACK_AUTHORING_BUDGET": str(self.budget),
            "DAVSTACK_AUTHORING_EVIDENCE": str(self.root),
        })
        env.start()
        self.addCleanup(env.stop)
        binaries = patch.object(native.shutil, "which", return_value="/fixture-only")
        binaries.start()
        self.addCleanup(binaries.stop)

    def receipt(self):
        paths = list(self.root.glob("run-*/result.json"))
        self.assertEqual(len(paths), 1, "every reserved failed trial must retain its result")
        result = json.loads(paths[0].read_text())
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertIs(result["native_process_stopped"], True)
        self.assertEqual(json.loads(self.budget.read_text())["used"], 1)
        return result

    def test_group_reservation_is_atomic_and_never_refunded(self):
        self.budget.write_text('{"limit":4,"used":0}')
        self.assertEqual(native.reserve_run(3), 3)
        with self.assertRaisesRegex(native.NativeRunError, "exhausted"):
            native.reserve_run(2)
        self.assertEqual(json.loads(self.budget.read_text())["used"], 3)

    def test_processes_cannot_overbook_the_shared_reservation_ledger(self):
        self.budget.write_text('{"limit":4,"used":0}')
        code = f"import runpy; n=runpy.run_path({str(SCRIPT)!r}); n['reserve_run'](3)"
        workers = [subprocess.Popen([sys.executable, "-B", "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        try:
            for worker in workers:
                worker.communicate(timeout=5)
            self.assertEqual(sorted(w.returncode for w in workers), [0, 1])
            self.assertEqual(json.loads(self.budget.read_text())["used"], 3)
        finally:
            for worker in workers:
                if worker.poll() is None:
                    worker.kill()
                    worker.wait()

    def test_expired_campaign_cannot_launch_or_extend_its_deadline(self):
        budget = {"limit": 12, "used": 2, "campaign_seconds": 900, "started_epoch": time.time() - 901, "started_monotonic": time.monotonic() - 901}
        self.budget.write_text(json.dumps(budget))
        with patch.object(native.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(native.NativeRunError, "campaign deadline"):
                native.run_trial("Never sent", "fixture/model", campaign_slots=2)
            launch.assert_not_called()
        self.assertEqual(json.loads(self.budget.read_text()), budget)

    def test_reserved_campaign_preparation_failure_does_not_refund_slots(self):
        self.budget.write_text('{"limit":12,"used":0,"campaign_seconds":900}')
        with patch.object(native.subprocess, "Popen") as launch:
            with self.assertRaises(native.NativeRunError):
                native.run_trial("Never sent", "fixture/model", campaign_slots=3, files={"../escaped": "no"})
            launch.assert_not_called()
        self.assertEqual(json.loads(self.budget.read_text())["used"], 3)

    def test_campaign_budget_requires_bounded_expiry_before_launch(self):
        with patch.object(native.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(native.NativeRunError, "campaign"):
                native.run_trial("Never sent", "fixture/model", campaign_slots=2)
            launch.assert_not_called()

    def test_skill_names_cannot_write_paths_or_inject_frontmatter(self):
        names = ["../escape", "../../../../escaped", str(self.root / "absolute"),
                 "nested/name", ".", "..", "bad\nname", "", "a" * 65]
        with patch.object(native.subprocess, "Popen", side_effect=OSError("unexpected launch")) as launch:
            for name in names:
                with self.subTest(name=name):
                    with self.assertRaisesRegex(native.NativeRunError, "skill name"):
                        native.run_trial("Never sent", "fixture/model", skill_name=name)
            launch.assert_not_called()
        self.assertEqual(list(self.root.rglob("SKILL.md")), [], "invalid names must not create any skill file")
        self.assertEqual(json.loads(self.budget.read_text())["used"], 0)

    def test_unwritable_evidence_does_not_consume_a_reservation(self):
        original_mkdir = Path.mkdir

        def refuse_trial(path, *args, **kwargs):
            if path.parent == self.root and path.name.startswith("run-"):
                raise PermissionError("fixture evidence directory refused")
            return original_mkdir(path, *args, **kwargs)

        with patch.object(Path, "mkdir", refuse_trial), patch.object(native.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(native.NativeRunError, "fixture evidence directory refused"):
                native.run_trial("Never sent", "fixture/model")
            launch.assert_not_called()
        self.assertEqual(json.loads(self.budget.read_text())["used"], 0)

    def test_launch_failure_retains_receipt_and_consumes_reservation(self):
        with patch.object(native.subprocess, "Popen", side_effect=OSError("fixture launch refused")):
            with self.assertRaisesRegex(native.NativeRunError, "fixture launch refused.*evidence:"):
                native.run_trial("Never sent", "fixture/model", skill_name="fixture-reader")
        result = self.receipt()
        self.assertIs(result["native_process_started"], False)
        self.assertIn("fixture launch refused", result["error"])
        self.assertTrue((Path(result["artifact_dir"]) / "work/.agents/skills/fixture-reader/SKILL.md").is_file())

    def test_preparation_failure_retains_receipt_without_launch(self):
        with patch.object(native.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(native.NativeRunError, "Fixture path.*evidence:"):
                native.run_trial("Never sent", "fixture/model", files={"../escaped.txt": "must not write"})
            launch.assert_not_called()
        result = self.receipt()
        self.assertIs(result["native_process_started"], False)
        self.assertEqual(list(self.root.rglob("escaped.txt")), [])

    def test_skill_path_cannot_follow_a_prepared_symlink(self):
        target = self.root / "outside-skills"
        target.mkdir()
        original_write = Path.write_text

        def prepare_link(path, content, *args, **kwargs):
            written = original_write(path, content, *args, **kwargs)
            if path.name == "seed":
                (path.parent / ".agents").mkdir()
                (path.parent / ".agents/skills").symlink_to(target, target_is_directory=True)
            return written

        with patch.object(Path, "write_text", prepare_link), patch.object(native.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(native.NativeRunError, "Skill path.*evidence:"):
                native.run_trial("Never sent", "fixture/model", skill_name="fixture-reader", files={"seed": "fixture"})
            launch.assert_not_called()
        self.assertEqual(list(target.rglob("SKILL.md")), [])
        self.receipt()

    def pipe_trial(self, flood):
        fixture = textwrap.dedent('''\
            import json, os, sys, time
            from pathlib import Path
            Path(os.environ['XDG_CACHE_HOME'], 'fixture.pid').write_text(str(os.getpid()))
            row = json.loads(sys.stdin.readline())
            print(json.dumps({'id': row['id'], 'result': {'engine': {'name': 'no-model fixture'}}}), flush=True)
        ''')
        if flood:
            fixture += "sys.stdout.write((json.dumps({'method': 'fixture.event', 'params': 'x' * 1000}) + '\\n') * 2000)\nsys.stdout.flush()\n"
            fixture += "row = json.loads(sys.stdin.readline())\nprint(json.dumps({'id': row['id'], 'error': 'fixture consumed request'}), flush=True)\n"
        fixture += "time.sleep(30)\n"
        worker = textwrap.dedent(f'''\
            import importlib.util, subprocess, sys
            from unittest.mock import patch
            spec = importlib.util.spec_from_file_location('native_fixture', {str(SCRIPT)!r})
            native = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(native)
            launch = subprocess.Popen
            def start_fixture(args, **kwargs):
                return launch([sys.executable, '-c', {fixture!r}], **kwargs)
            with patch.object(native.shutil, 'which', return_value='/fixture-only'), patch.object(native.subprocess, 'Popen', side_effect=start_fixture):
                try:
                    native.run_trial('Never sent to a model. ' * 100000, 'fixture/model', timeout=1)
                except native.NativeRunError as error:
                    print(error)
        ''')
        process = subprocess.Popen([sys.executable, "-B", "-c", worker], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=4)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            self.fail("native helper exceeded its deadline while writing RPC input; watchdog stopped owned processes")
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        self.assertEqual(process.returncode, 0, stderr)
        expected = "fixture consumed request" if flood else "deadline"
        self.assertIn(expected, stdout)
        result = self.receipt()
        self.assertIn(expected, result["error"])
        pid = int(next(self.root.glob("run-*/cache/fixture.pid")).read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_stalled_rpc_input_is_bounded_and_process_is_reaped(self):
        self.pipe_trial(flood=False)

    def test_rpc_output_is_drained_while_input_is_blocked(self):
        self.pipe_trial(flood=True)


if __name__ == "__main__":
    unittest.main()
