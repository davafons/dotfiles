"""Check campaign admission with scripted replies and a private workspace."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

class Campaign(unittest.TestCase):
    def run_fixture(self, invalid):
        binary = os.environ.get('YUKE_BINARY') or shutil.which('yuke-rust')
        if binary is None:
            self.skipTest('Set YUKE_BINARY to test campaign hooks.')
        with tempfile.TemporaryDirectory(prefix='yuke-campaign-', dir='/tmp') as directory:
            workspace = str(Path(directory).resolve())
            grant = dict(slots=2, deadline_ms=int(time.time() * 1000) + 40000, nonce='a' * 32, workspace=workspace, home=workspace, max_concurrent=1)
            result = subprocess.run([binary, 'test', str(Path(__file__).resolve().parents[1] / 'scripts/campaign.test.ts')], capture_output=True, text=True, timeout=15, env=dict(os.environ, DAVSTACK_CAMPAIGN='invalid' if invalid else json.dumps(grant), CAMPAIGN_FIXTURE_WORKSPACE=workspace, CAMPAIGN_EXPECT_INVALID='1' if invalid else '0', XDG_CACHE_HOME=workspace + '/cache'))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            if not invalid:
                self.assertEqual(json.loads((Path(workspace) / 'cache/campaign-ready.json').read_text()), grant)

    def test_valid_grant_limits_the_model_catalog_and_tool_execution(self):
        self.run_fixture(False)

    def test_invalid_grant_stops_before_a_model_request(self):
        self.run_fixture(True)

if __name__ == '__main__':
    unittest.main()
