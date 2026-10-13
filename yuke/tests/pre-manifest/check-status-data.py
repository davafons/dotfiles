#!/usr/bin/env python3
"""Pin quota meaning, credential routing, and secret-free failure output."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

PLUGIN = Path(__file__).resolve().parents[2] / ".config/yuke/plugins/status-data.py"
spec = importlib.util.spec_from_file_location("status_data", PLUGIN)
data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data)

PAYLOAD = {"plan_type": "plus", "rate_limit": {
    "primary_window": {"used_percent": 7, "limit_window_seconds": 604800, "reset_at": 1792327366},
    "secondary_window": None}, "credits": {"has_credits": True, "unlimited": False, "balance": "9915.4961790000"}}


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name)
        self.row = {"id": "openai-codex", "auth": {"oauth": {
            "access_token": "SECRET_TOKEN", "account_id": "SECRET_ACCOUNT", "expires_at_ms": 9000000000000}}}
        self.save(self.row)

    def save(self, row):
        self.path = self.config / "providers.json"
        self.path.write_text(json.dumps({"providers": [row]}))
        self.path.chmod(0o600)

    def test_weekly_primary_is_not_a_five_hour_window_or_token_balance(self):
        with patch.object(data, "read_json", return_value=PAYLOAD) as fetch:
            result = data.snapshot("openai-codex", self.config)
        self.assertEqual(result["state"], "reported")
        self.assertEqual(result["windows"], [{"label": "Codex Weekly limit", "remainingPercent": 93,
                         "windowSeconds": 604800, "resetsAt": 1792327366}])
        self.assertAlmostEqual(result["creditBalance"], 9915.496179)
        self.assertIn("No separate 5h limit was reported.", result["notes"])
        self.assertNotIn("SECRET", json.dumps(result))
        url, headers = fetch.call_args.args
        self.assertEqual(url, "https://chatgpt.com/backend-api/wham/usage")
        self.assertEqual(headers["ChatGPT-Account-Id"], "SECRET_ACCOUNT")
        self.assertEqual(headers["Authorization"], "Bearer SECRET_TOKEN")
        self.assertEqual(json.loads(self.path.read_text())["providers"][0], self.row)

    def test_additional_limits_and_zero_remaining_are_not_hidden(self):
        result = data.codex_snapshot({"rate_limit": {"limit_reached": True,
            "primary_window": {"used_percent": 100, "limit_window_seconds": 18000, "reset_at": 12345},
            "secondary_window": {"used_percent": 35, "limit_window_seconds": 604800}},
            "additional_rate_limits": [{"limit_name": "Model B", "rate_limit": {
                "primary_window": {"used_percent": 4, "limit_window_seconds": 3600}}}],
            "credits": {"balance": "0", "unlimited": False}})
        self.assertEqual([row["remainingPercent"] for row in result["windows"]], [0, 65, 96])
        self.assertEqual(result["windows"][2]["label"], "Model B 1h limit")
        self.assertEqual(result["creditBalance"], 0)
        self.assertTrue(any("exhausted" in note for note in result["notes"]))

    def test_missing_and_invalid_windows_do_not_become_full_allowances(self):
        for used in (None, True, "3", -1, 101, float("nan")):
            result = data.codex_snapshot({"rate_limit": {"primary_window": {
                "used_percent": used, "limit_window_seconds": 18000}}, "credits": {"balance": "NaN"}})
            self.assertEqual(result["windows"], [])
            self.assertIsNone(result["creditBalance"])
        self.assertEqual(data.codex_snapshot({})["windows"], [])
        self.assertTrue(data.codex_snapshot({"credits": {"unlimited": True}})["unlimitedCredits"])

    def test_custom_route_expiry_and_unsupported_provider_send_no_credentials(self):
        with patch.object(data, "read_json") as fetch:
            self.row["base_url"] = "https://gateway.example/v1"
            self.save(self.row)
            self.assertEqual(data.snapshot("openai-codex", self.config)["state"], "unavailable")
            del self.row["base_url"]
            self.row["auth"]["oauth"]["expires_at_ms"] = 1
            self.save(self.row)
            self.assertIn("expired", data.snapshot("openai-codex", self.config)["error"])
            self.assertEqual(data.snapshot("anthropic", self.config)["state"], "unavailable")
            fetch.assert_not_called()

    def test_private_file_and_symlink_checks_run_before_network(self):
        with patch.object(data, "read_json") as fetch:
            self.path.chmod(0o644)
            self.assertEqual(data.snapshot("openai-codex", self.config)["state"], "error")
            target = self.config / "target.json"
            self.path.rename(target)
            self.path.symlink_to(target)
            self.assertEqual(data.snapshot("openai-codex", self.config)["state"], "error")
            fetch.assert_not_called()

    def test_openrouter_cap_is_not_an_account_balance(self):
        self.save({"id": "openrouter", "auth": {"api_key": {"source": {"env": "TEST_ROUTER_KEY"}}}})
        with patch.dict(os.environ, {"TEST_ROUTER_KEY": "SECRET"}), patch.object(data, "read_json", return_value={"data": {
            "limit_remaining": 12.75, "free_model_daily_requests": {"remaining": 23}}}) as fetch:
            result = data.snapshot("openrouter", self.config)
        self.assertEqual(result["keyRemaining"], 12.75)
        self.assertEqual(result["requestsRemaining"], 23)
        self.assertIsNone(result["creditBalance"])
        self.assertEqual(fetch.call_args.args[0], "https://openrouter.ai/api/v1/key")
        self.assertIsNone(data.openrouter_snapshot({"data": {"limit_remaining": None}})["keyRemaining"])

    def test_explicit_empty_key_does_not_fall_back_to_environment(self):
        self.save({"id": "openrouter", "auth": {"api_key": {}}})
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "SECRET"}), patch.object(data, "read_json") as fetch:
            self.assertEqual(data.snapshot("openrouter", self.config)["state"], "error")
            fetch.assert_not_called()

    def test_xai_weekly_pool_is_remaining_percent_not_a_token_balance(self):
        self.save({"id": "xai-grok", "auth": {"oauth": {"access_token": "SECRET_TOKEN", "expires_at_ms": 9000000000000}}})
        payload = {"config": {"creditUsagePercent": 74, "currentPeriod": {
            "type": "USAGE_PERIOD_TYPE_WEEKLY", "start": "2026-10-10T16:25:20.272285+00:00",
            "end": "2026-10-17T16:25:20.272285+00:00"}, "onDemandCap": {"val": 0}, "onDemandUsed": {"val": 0},
            "prepaidBalance": {"val": 0}, "productUsage": [{"product": "GrokBuild", "usagePercent": 74}]}}
        with patch.object(data, "read_json", return_value=payload) as fetch:
            result = data.snapshot("xai-grok", self.config)
        self.assertEqual(result["state"], "reported")
        self.assertEqual(result["windows"], [{"label": "Weekly limit", "remainingPercent": 26,
                         "windowSeconds": 604800, "resetsAt": 1792254320}])
        self.assertIsNone(result["creditBalance"])
        self.assertIn("not an exact remaining-token balance.", result["notes"][0])
        self.assertIn("GrokBuild accounts for 74% of reported pool usage.", result["notes"])
        self.assertNotIn("SECRET", json.dumps(result))
        url, headers = fetch.call_args.args
        self.assertEqual(url, "https://cli-chat-proxy.grok.com/v1/billing?format=credits")
        self.assertEqual(headers["Authorization"], "Bearer SECRET_TOKEN")
        self.assertEqual(headers["x-xai-token-auth"], "xai-grok-cli")

    def test_xai_missing_or_invalid_percent_does_not_become_a_full_allowance(self):
        omitted = data.xai_snapshot({"config": {"currentPeriod": {"type": "USAGE_PERIOD_TYPE_WEEKLY",
            "start": "2026-10-10T00:00:00Z", "end": "2026-10-17T00:00:00Z"}, "onDemandCap": {"val": 0}}})
        self.assertEqual(omitted["windows"], [])
        self.assertTrue(any("did not report" in note for note in omitted["notes"]))
        invalid = data.xai_snapshot({"config": {"creditUsagePercent": 140, "onDemandCap": {"val": 100},
                                                "onDemandUsed": {"val": 1}}})
        self.assertEqual(invalid["windows"], [])
        self.assertTrue(any("invalid quota" in note for note in invalid["notes"]))
        fallback = data.xai_snapshot({"config": {"onDemandCap": {"val": 1000}, "onDemandUsed": {"val": 250}}})
        self.assertEqual(fallback["windows"][0]["remainingPercent"], 75)
        self.assertEqual(fallback["windows"][0]["label"], "Usage pool")

    def test_xai_custom_route_and_expiry_send_no_credentials(self):
        self.save({"id": "xai-grok", "base_url": "https://gateway.example/v1",
                   "auth": {"oauth": {"access_token": "SECRET_TOKEN", "expires_at_ms": 9000000000000}}})
        with patch.object(data, "read_json") as fetch:
            self.assertEqual(data.snapshot("xai-grok", self.config)["state"], "unavailable")
            self.save({"id": "xai-grok", "auth": {"oauth": {"access_token": "SECRET_TOKEN", "expires_at_ms": 1}}})
            self.assertIn("expired", data.snapshot("xai-grok", self.config)["error"])
            fetch.assert_not_called()

    def test_error_bodies_and_redirects_never_reach_output(self):
        opener = unittest.mock.Mock()
        for code in (401, 403, 429, 500):
            opener.open.side_effect = urllib.error.HTTPError("https://quota", code, "SECRET_BODY", {}, None)
            with patch.object(data.urllib.request, "build_opener", return_value=opener):
                result = data.snapshot("openai-codex", self.config)
            self.assertEqual(result["state"], "error")
            self.assertIn(str(code), result["error"])
            self.assertNotIn("SECRET", json.dumps(result))
        with self.assertRaises(data.StatusError):
            data.NoRedirect().redirect_request(None, None, 302, "SECRET", {}, "https://other.example")


if __name__ == "__main__":
    unittest.main()
