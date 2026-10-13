"""Exercise native trigger observations and budget refusal without real model calls."""
import http.server
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
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
                if "OBSERVE_READ" in text:
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


if __name__ == "__main__":
    unittest.main()
