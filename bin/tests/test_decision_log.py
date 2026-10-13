import csv
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
LOGGER = ROOT / "agents/.agents/davstack/skills/show-me-your-work/scripts/log.sh"


class DecisionLog(unittest.TestCase):
    def run_logger(self, logfile, *cells):
        return subprocess.run(
            ["/bin/bash", str(LOGGER), str(logfile), *cells],
            capture_output=True, text=True, timeout=5,
        )

    def test_creates_parent_and_preserves_prior_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            logfile = Path(temporary) / "nested/decisions.tsv"
            first = self.run_logger(logfile, "frame", "Keep upstream", "Native tools only", "source.patch", "open")
            self.assertEqual(first.returncode, 0, first.stderr)
            before = logfile.read_bytes()
            second = self.run_logger(logfile, "verify", "Run the helper", "Check real output", "result.json", "PASS")
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertTrue(logfile.read_bytes().startswith(before))
            rows = logfile.read_text().splitlines()
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0], "ts\tphase\tdecision\twhy\tevidence\tresult")
            self.assertRegex(rows[1].split("\t")[0], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
            self.assertEqual(rows[1].split("\t")[1:], ["frame", "Keep upstream", "Native tools only", "source.patch", "open"])
            self.assertEqual(rows[2].split("\t")[1:], ["verify", "Run the helper", "Check real output", "result.json", "PASS"])

    def test_escapes_each_formula_prefix_in_every_cell(self):
        with tempfile.TemporaryDirectory() as temporary:
            logfile = Path(temporary) / "decisions.tsv"
            for prefix in ("=", "+", "-", "@"):
                result = self.run_logger(logfile, *([prefix + "value"] * 5))
                self.assertEqual(result.returncode, 0, result.stderr)
            rows = logfile.read_text().splitlines()
            self.assertEqual(len(rows), 5)
            self.assertEqual([row.split("\t")[1:] for row in rows[1:]], [
                ["'=value"] * 5, ["'+value"] * 5, ["'-value"] * 5, ["'@value"] * 5,
            ])

    def test_keeps_tabs_newlines_and_carriage_returns_inside_one_cell(self):
        with tempfile.TemporaryDirectory() as temporary:
            logfile = Path(temporary) / "decisions.tsv"
            result = self.run_logger(logfile, "phase\tvalue", "first\nsecond", "why\rvalue", "🧭 evidence", "")
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = logfile.read_text().splitlines()
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1].split("\t")[1:], ["phase value", "first second", "why value", "🧭 evidence", ""])

    def test_preserves_literal_shell_data_and_awkward_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            logfile = Path(temporary) / "a ' quoted directory" / "log $value.tsv"
            sentinel = Path(temporary) / "must-not-exist"
            value = f"$(touch '{sentinel}')"
            result = self.run_logger(logfile, "phase", value, "literal data", "artifact", "PASS")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(sentinel.exists())
            self.assertEqual(logfile.read_text().splitlines()[1].split("\t")[2], value)

    def test_rejects_wrong_arity_without_changing_the_log(self):
        with tempfile.TemporaryDirectory() as temporary:
            logfile = Path(temporary) / "decisions.tsv"
            for cells in ((), ("one",), ("one",) * 6):
                result = self.run_logger(logfile, *cells)
                self.assertEqual(result.returncode, 1)
                self.assertIn("usage: log.sh", result.stderr)
                self.assertFalse(logfile.exists())

    def test_links_canonical_decisions_to_complete_attempt_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            attempts = Path(temporary) / "attempts.tsv"
            logfile = Path(temporary) / "decisions.tsv"
            fields = ["id", "hypothesis", "change", "before", "after", "delta", "tests", "verdict", "note"]
            records = [
                ["1", "Avoid repeated parsing", "Cache parsed input", "100", "80", "-20", "green", "kept", "Literal fixture data"],
                ["2", "Reduce allocations", "Reuse buffer", "80", "79", "-1", "failed", "reverted", "Regression gate failed"],
            ]
            with attempts.open("w", newline="") as artifact:
                writer = csv.writer(artifact, delimiter="\t")
                writer.writerow(fields)
                writer.writerows(records)
            artifact_before = attempts.read_bytes()
            for record, why in zip(records, ["Gate green and metric past noise", "Regression gate failed"]):
                result = self.run_logger(
                    logfile, "attempt", f"Attempt {record[0]}: {record[2]}",
                    why, f"{attempts}#id={record[0]}", record[7],
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(attempts.read_bytes(), artifact_before)
            with logfile.open(newline="") as log:
                rows = list(csv.reader(log, delimiter="\t"))
            self.assertEqual(rows[0], ["ts", "phase", "decision", "why", "evidence", "result"])
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[1][1:], [
                "attempt", "Attempt 1: Cache parsed input", "Gate green and metric past noise",
                f"{attempts}#id=1", "kept",
            ])
            self.assertEqual(rows[2][1:], [
                "attempt", "Attempt 2: Reuse buffer", "Regression gate failed",
                f"{attempts}#id=2", "reverted",
            ])
            for row, expected in zip(rows[1:], records):
                self.assertEqual(len(row), 6)
                artifact_path, attempt_id = row[4].split("#id=")
                with Path(artifact_path).open(newline="") as artifact:
                    retrieved = list(csv.DictReader(artifact, delimiter="\t"))
                attempt = next(item for item in retrieved if item["id"] == attempt_id)
                self.assertEqual([attempt[field] for field in fields], expected)
                self.assertEqual(attempt["verdict"], row[5])

    def test_uses_an_existing_empty_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            logfile = Path(temporary) / "decisions.tsv"
            logfile.touch()
            result = self.run_logger(logfile, "phase", "decision", "why", "evidence", "PASS")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(logfile.read_text().splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
