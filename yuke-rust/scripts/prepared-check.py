#!/usr/bin/env python3
"""Check copied state and load the prepared profile without refreshing credentials or sending input."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary', type=Path, required=True)
parser.add_argument('--appname', default='yuke-rust')
args = parser.parse_args()
home = Path.home()
config_root = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))
data_root = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share'))
state_root = Path(os.environ.get('XDG_STATE_HOME', home / '.local/state'))
profile, data = config_root / args.appname, data_root / args.appname

def tables(path):
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as connection:
        assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        names = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {name: sorted(connection.execute('SELECT * FROM "' + name.replace('"', '""') + '"').fetchall(), key=repr) for name in names}

for old, new in [('work/work.sqlite3', 'plugins/project-work/work.sqlite3'), ('clarify/questions.sqlite3', 'plugins/yuke-clarify/questions.sqlite3')]:
    source, target = state_root / 'yuke' / old, data / new
    if source.exists():
        expected, actual = tables(source), tables(target)
        assert expected == actual, f'State differs: {new}'
        print(f'PASS copied state: {new} ({sum(map(len, actual.values()))} rows)')
for path in [profile / 'providers.json', profile / 'monid.key', data / 'auth.json']:
    if path.exists():
        assert stat.S_IMODE(path.stat().st_mode) == 0o600, f'Private file permissions: {path.name}'
source_aliases = config_root / 'yuke/model-aliases.json'
if source_aliases.exists():
    assert json.loads(source_aliases.read_text()) == json.loads((data / 'plugins/models/model-aliases.json').read_text())
archive = data / 'plugins/insights/zig-usage.json'
if archive.exists():
    assert 'chats' not in json.loads(archive.read_text()), 'The usage archive must contain only aggregate data.'
requests = [
    dict(id=1, method='initialize', params=dict(protocolVersion=1, clientInfo=dict(name='migration-check', version='1'))),
    dict(id=2, method='catalog/list', params={}),
    dict(id=3, method='plugin/list', params={}),
    dict(id=4, method='session/list', params={}),
]
with tempfile.TemporaryDirectory(prefix='yuke-prepared-check-') as directory:
    result = subprocess.run([str(args.binary.resolve()), '--rpc'], input=''.join(json.dumps(dict(jsonrpc='2.0', **request)) + '\n' for request in requests), text=True, capture_output=True, cwd=directory, env=dict(os.environ, YUKE_APPNAME=args.appname), timeout=30)
assert result.returncode == 0, 'The native profile check failed.'
messages = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
answers = {message['id']: message.get('result') for message in messages if 'id' in message}
assert all(answers.get(number) is not None for number in range(1, 5)), 'A native request failed.'
assert not [message for message in messages if message.get('method') == 'notice' and message.get('params', {}).get('level') == 'error'], 'A plugin reported an error.'
assert answers[4]['sessions'] == [], 'The new profile must start with fresh chats.'
plugins = answers[3]['plugins']
assert len(plugins) == 26 and all(plugin['loaded'] for plugin in plugins), 'A plugin did not load.'
providers = answers[2]['providers']
ready = {provider['id'] for provider in providers}
assert {'openai-codex', 'xai-grok', 'claude-bridge'} <= ready, 'A configured provider is missing.'
bridge = next(provider for provider in providers if provider['id'] == 'claude-bridge')
assert {'opus', 'sonnet', 'haiku', 'fable'} <= {model['id'] for model in bridge['models']}
assert all('image' in model['input'] and model['tools'] for model in bridge['models']), 'Bridge capabilities differ.'
print('PASS native profile: 26 loaded plugins, ready providers, bridge image/tools metadata, zero chats')
print('PASS aliases, private file permissions, aggregate-only Zig usage archive')
