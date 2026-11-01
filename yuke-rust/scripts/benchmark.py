#!/usr/bin/env python3
"""Compare the public frame/input path in two release binaries, with work assertions on every run."""
import argparse
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import tempfile
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
fixture = Path(__file__).with_name('render-benchmark.test.ts')
args.output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='yuke-benchmark-', dir='/tmp') as directory:
    environment = dict(os.environ, HOME=directory, XDG_CONFIG_HOME=directory + '/config', XDG_DATA_HOME=directory + '/data', YUKE_APPNAME='benchmark')
    # The profiler changes timing, so this run is excluded from the comparison.
    profile = subprocess.Popen([str(args.candidate.resolve()), 'test', str(fixture)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=dict(environment, YUKE_BENCH_ITERATIONS='1200'))
    time.sleep(0.1)
    sampled = subprocess.run(['/usr/bin/sample', str(profile.pid), '1', '1', '-file', str(args.output / 'sample.txt')], capture_output=True, text=True)
    stdout, stderr = profile.communicate(timeout=15)
    assert profile.returncode == 0 and '2 passed, 0 failed' in stdout + stderr, stdout + stderr
    (args.output / 'sample-command.log').write_text(sampled.stdout + sampled.stderr)
    rows = []
    for index in range(5):
        for name, binary in [('baseline', args.baseline), ('candidate', args.candidate)]:
            result = subprocess.run(['/usr/bin/time', '-lp', str(binary.resolve()), 'test', str(fixture)], capture_output=True, text=True, env=environment, timeout=15)
            output = result.stdout + result.stderr
            (args.output / f'{index}-{name}.log').write_text(output)
            assert result.returncode == 0 and '2 passed, 0 failed' in output, output
            values = {key: float(value) for key, value in re.findall(r'^(real|user|sys)\s+([0-9.]+)$', output, re.M)}
            memory = re.search(r'(\d+)\s+maximum resident set size', output)
            assert memory is not None and set(values) == {'real', 'user', 'sys'}, output
            rows.append(dict(side=name, run=index, rssBytes=int(memory[1]), **values))
    report = dict(iterations=300, transcriptFrames=300, inputFrames=600, checkedRows=9000, testsPerRun=2, alternatingRuns=5, failures=0, profileCaptured=sampled.returncode == 0, runs=rows, summary={})
    for name in ['baseline', 'candidate']:
        side = [row for row in rows if row['side'] == name]
        report['summary'][name] = {field: dict(median=statistics.median(row[field] for row in side), minimum=min(row[field] for row in side), maximum=max(row[field] for row in side)) for field in ['real', 'user', 'sys', 'rssBytes']}
    (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['summary'], indent=2))
