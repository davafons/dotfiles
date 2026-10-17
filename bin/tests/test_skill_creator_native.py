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
