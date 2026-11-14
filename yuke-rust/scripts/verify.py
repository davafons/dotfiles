#!/usr/bin/env python3
"""Run the migration checks. Each command writes a separate log under the Rust target directory."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=Path.home() / 'workspace/yuke')
parser.add_argument('--binary', type=Path)
parser.add_argument('--native', action='store_true', help='Also run all required native workspace checks.')
args = parser.parse_args()
source = args.source.resolve(strict=True)
root = Path(__file__).resolve().parents[1]
binary = (args.binary or source / 'target/debug/yuke').resolve(strict=True)
logs = source / 'target/migration-verification'
logs.mkdir(parents=True, exist_ok=True)
environment = dict(os.environ, MONID_API_KEY='migration-fixture-key', YUKE_BINARY=str(binary))
checks = [
    ('profile-types', ['python3', str(root / 'tests/typecheck.py'), '--source', str(source)]),
    ('profile-biome', ['mise', 'exec', '--', 'biome', 'ci', '--error-on-warnings', '--config-path', str(root / 'biome.json'), str(root / '.config/yuke-rust'), str(root / 'tests'), str(root / 'scripts')]),
    ('profile-tools', [str(binary), 'test', str(root / 'tests')]),
    ('vim', [str(binary), 'test', str(root / '.config/yuke-rust/plugins/vim/tests')]),
    ('stores', ['python3', '-m', 'unittest', 'discover', '-s', str(root / 'tests'), '-p', 'test_*.py']),
    ('terminal', ['python3', str(root / 'tests/terminal.py')]),
    ('agent-tools', ['python3', str(root / 'tests/check-agent-tools.py'), '--binary', str(binary)]),
]
if args.native:
    checks += [
        ('format', ['mise', 'exec', '--', 'cargo', 'fmt', '--all', '--', '--check']),
        ('clippy', ['mise', 'exec', '--', 'cargo', 'clippy', '--all-targets', '--all-features', '--', '-D', 'warnings']),
        ('workspace', ['mise', 'exec', '--', 'cargo', 'test', '--all-features']),
        ('rustdoc', ['mise', 'exec', '--', 'env', 'RUSTDOCFLAGS=-Dwarnings', 'cargo', 'doc', '--no-deps', '--all-features']),
        ('native-types', ['mise', 'exec', '--', 'tsc', '-p', 'crates/js/tsconfig.json']),
        ('biome', ['mise', 'exec', '--', 'biome', 'ci', '--error-on-warnings']),
    ]
    checks += [(path.parent.name, ['mise', 'exec', '--', 'cargo', 'check', '--manifest-path', str(path), '--all-targets']) for path in sorted((source / 'crates').glob('*/Cargo.toml'))]
for name, command in checks:
    path = logs / (name + '.log')
    with path.open('w') as output:
        result = subprocess.run(command, cwd=source, env=environment, stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        print(f'FAIL {name}: {path}', flush=True)
        print('\n'.join(path.read_text().splitlines()[-30:]))
        sys.exit(result.returncode)
    print(f'PASS {name}: {path}', flush=True)
