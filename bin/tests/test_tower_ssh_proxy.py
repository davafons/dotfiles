import importlib.machinery
import importlib.util
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch


loader = importlib.machinery.SourceFileLoader("tower_ssh_proxy", str(Path(__file__).parents[1] / "bin/tower-ssh-proxy"))
spec = importlib.util.spec_from_loader(loader.name, loader)
proxy = importlib.util.module_from_spec(spec)
loader.exec_module(proxy)


class TowerSshProxyTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ssh"), "OpenSSH is required")
    def test_only_explicit_alias_configures_wake(self):
        config = Path(__file__).parents[2] / "ssh/.ssh/config"
        for alias in ("tower", "tower-lan", "tower-tailnet", "tower-wake"):
            with self.subTest(alias=alias):
                result = subprocess.run(
                    ["ssh", "-G", "-F", str(config), alias],
                    capture_output=True, text=True, check=True, timeout=10,
                )
                options = dict(line.split(" ", 1) for line in result.stdout.splitlines())
                if alias == "tower-wake":
                    self.assertIn("tower-ssh-proxy", options["proxycommand"])
                    self.assertEqual(options["hostkeyalias"], proxy.TAILNET)
                else:
                    self.assertIn(options.get("proxycommand"), (None, "none"))
                    self.assertEqual(options["connecttimeout"], "8")

    def test_awake_host_connects_without_wake(self):
        with patch.object(proxy, "ready_route", return_value=proxy.LAN), patch.object(proxy, "wake") as wake, patch.object(proxy.os, "execvp") as execute:
            proxy.connect("tower-wake", proxy.TAILNET, 22)
        wake.assert_not_called()
        execute.assert_called_once_with("nc", ["nc", proxy.LAN, "22"])

    def test_sleeping_host_wakes_once_then_connects(self):
        with patch.object(proxy, "ready_route", side_effect=[None, None, proxy.LAN]), patch.object(proxy, "wake") as wake, patch.object(proxy.time, "sleep"), patch.object(proxy.os, "execvp") as execute:
            proxy.connect("tower-wake", proxy.TAILNET, 22)
        wake.assert_called_once_with()
        execute.assert_called_once_with("nc", ["nc", proxy.LAN, "22"])

    def test_wake_alias_prefers_lan_then_tailnet(self):
        with patch.object(proxy, "ready_route", return_value=proxy.TAILNET) as probe, patch.object(proxy.os, "execvp"):
            proxy.connect("tower-wake", proxy.TAILNET, 22)
        probe.assert_called_once_with((proxy.LAN, proxy.TAILNET), 22)

    def test_failed_wake_times_out_without_connecting(self):
        with patch.object(proxy, "ready_route", return_value=None), patch.object(proxy, "wake"), patch.object(proxy.time, "monotonic", side_effect=[0, 91]), patch.object(proxy.os, "execvp") as execute:
            with self.assertRaisesRegex(RuntimeError, "within 90 seconds"):
                proxy.connect("tower-wake", proxy.TAILNET, 22)
        execute.assert_not_called()

    def test_other_hosts_never_trigger_wake(self):
        with patch.object(proxy, "wake") as wake:
            for alias in ("tower", "tower-lan", "tower-tailnet", "qtower"):
                with self.subTest(alias=alias), self.assertRaises(RuntimeError):
                    proxy.connect(alias, proxy.LAN, 22)
        wake.assert_not_called()


if __name__ == "__main__":
    unittest.main()
