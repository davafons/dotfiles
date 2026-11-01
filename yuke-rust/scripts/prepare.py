#!/usr/bin/env python3
"""Prepare a separate Rust profile. Keep the Zig executable, profile, and chat store in place."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def private_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        os.chmod(temporary.name, 0o600)
        temporary.write(value)
        temporary.flush()
        os.fsync(temporary.fileno())
        name = temporary.name
    os.replace(name, path)


def private_json(path, value):
    private_write(path, (json.dumps(value, indent=2) + '\n').encode())


def providers(legacy):
    """Translate only public provider fields. Credentials go to the separate Rust auth file."""
    changes, credentials = [], {}
    for old in legacy.get('providers', []):
        entry = {key: old[key] for key in ('id', 'name', 'base_url', 'headers', 'session_header') if key in old}
        auth = old.get('auth', {})
        if 'oauth' in auth:
            grant = auth['oauth']
            credentials[old['id']] = {key: grant[key] for key in ('access_token', 'refresh_token', 'account_id') if key in grant}
            credentials[old['id']]['expires_at'] = grant['expires_at_ms']
        if 'api_key' in old:
            credentials[old['id']] = {'api_key': old['api_key']}
        if 'api_key' in auth:
            source = auth['api_key'].get('source', {})
            if 'literal' in source:
                credentials[old['id']] = {'api_key': source['literal']}
            elif 'env' in source:
                entry['api_key_env'] = source['env']
            else:
                raise ValueError('Unsupported API key source for ' + old['id'])
        if 'endpoints' in old:
            entry['endpoints'] = []
            for endpoint in old['endpoints']:
                item = {'protocol': endpoint['protocol']}
                for key in ('credential_header',):
                    if key in endpoint:
                        item[key] = endpoint[key]
                if endpoint.get('cache') == 'breakpoint':
                    item['cache_breakpoint'] = True
                if endpoint['protocol'] == 'openai_responses' and 'responses_dialect' in endpoint:
                    item['responses_dialect'] = endpoint['responses_dialect']
                if endpoint['protocol'] == 'openai_chat' and 'chat_dialect' in endpoint:
                    item['chat_dialect'] = endpoint['chat_dialect']
                entry['endpoints'].append(item)
        if 'models' in old:
            entry['models'] = []
            for model in old['models']:
                item = {key: model[key] for key in ('id', 'upstream_id', 'name', 'protocol', 'limits', 'cost', 'reasoning_levels') if key in model}
                protocol = model.get('protocol') or entry['endpoints'][0]['protocol']
                flags = model.get('flags', {})
                item['flags'] = {key: flags[key] for key in ('supports_tool_search', 'can_disable_reasoning', 'supports_cache_breakpoint') if key in flags}
                keys = ('anthropic_thinking', 'reasoning_budget_min', 'reasoning_budget_max') if protocol == 'anthropic_messages' else ('thinking_format', 'reasoning_replay', 'max_tokens_field') if protocol == 'openai_chat' else ()
                item['flags'].update({key: flags[key] for key in keys if key in flags})
                if 'supports_vision' in flags:
                    item['input'] = ['text', 'image'] if flags['supports_vision'] else ['text']
                    item['output'] = ['text']
                if 'supports_tools' in flags:
                    item['tools'] = flags['supports_tools']
                entry['models'].append(item)
        if len(entry) > 1:
            changes.append(entry)
    return {'providers': changes}, credentials


def snapshot(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        pending = Path(temporary) / 'snapshot.db'
        with sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True) as old:
            with sqlite3.connect(pending) as new:
                old.backup(new)
                result = new.execute('PRAGMA integrity_check').fetchone()[0]
                if result != 'ok':
                    raise ValueError('The database snapshot failed its integrity check.')
        os.chmod(pending, 0o600)
        os.replace(pending, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--appname', default='yuke-rust')
    parser.add_argument('--refresh-state', action='store_true', help='Refresh only prepared state that Rust has not changed.')
    args = parser.parse_args()
    if args.appname in ('.', '..', 'yuke') or any(char in args.appname for char in '/\\\0'):
        parser.error('use a separate plain app name')
    home = args.home.resolve(strict=True)
    def root(variable, fallback):
        value = Path(os.environ.get(variable, ''))
        return value if value.is_absolute() else home / fallback
    config_root, data_root, state_root = root('XDG_CONFIG_HOME', '.config'), root('XDG_DATA_HOME', '.local/share'), root('XDG_STATE_HOME', '.local/state')
    legacy = config_root / 'yuke'
    profile, data = config_root / args.appname, data_root / args.appname
    manifest_path = data / 'migration.json'
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    written = dict(previous.get('state', {}))
    source = ROOT / '.config/yuke-rust'
    if not legacy.is_dir():
        parser.error('the Zig profile does not exist')
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copytree(source, profile, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    config = json.loads((profile / 'config.json').read_text())
    settings_file = legacy / 'plugins/models/settings.json'
    settings = json.loads(settings_file.read_text()) if settings_file.exists() else {}
    config['plugins'] = [{'path': entry, 'options': settings} if entry == './plugins/models' else entry for entry in config['plugins']]
    private_json(profile / 'config.json', config)
    private_json(profile / 'tsconfig.json', {'extends': str(home / '.local/lib/yuke-rust/tsconfig.json'), 'include': ['**/*.ts', '**/*.js'], 'compilerOptions': {'allowJs': True, 'checkJs': True}})
    old_config = json.loads((legacy / 'config.json').read_text())
    if 'systemPrompt' in old_config:
        private_json(profile / 'plugins/personal/prompt.json', old_config['systemPrompt'])
    changes, credentials = providers(json.loads((legacy / 'providers.json').read_text()))
    private_json(profile / 'providers.json', changes)
    aliases = legacy / 'model-aliases.json'
    if aliases.exists():
        target = data / 'plugins/models/model-aliases.json'
        if not target.exists():
            private_write(target, aliases.read_bytes())
            written[str(target.relative_to(data))] = digest(target)
    key = legacy / 'monid.key'
    if key.exists():
        private_write(profile / 'monid.key', key.read_bytes())
    auth = data / 'auth.json'
    if not auth.exists() or args.refresh_state and written.get('auth.json') == digest(auth):
        private_json(auth, credentials)
        written['auth.json'] = digest(auth)
    for name, target_name in [('work/work.sqlite3', 'plugins/project-work/work.sqlite3'), ('clarify/questions.sqlite3', 'plugins/yuke-clarify/questions.sqlite3')]:
        old, target = state_root / 'yuke' / name, data / target_name
        if old.exists() and (not target.exists() or args.refresh_state and written.get(target_name) == digest(target)):
            snapshot(old, target)
            written[target_name] = digest(target)
    usage_target = data / 'plugins/insights/zig-usage.json'
    usage_reader = legacy / 'plugins/usage-data.py'
    usage_database = data_root / 'yuke/yuke.db'
    if usage_reader.is_file() and usage_database.is_file() and (not usage_target.exists() or args.refresh_state and written.get('plugins/insights/zig-usage.json') == digest(usage_target)):
        specification = importlib.util.spec_from_file_location('legacy_usage', usage_reader)
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        aggregates = module.snapshot(usage_database)
        aggregates.pop('chats', None)
        private_json(usage_target, aggregates)
        written['plugins/insights/zig-usage.json'] = digest(usage_target)
    private_json(manifest_path, dict(version=1, preparedAt=datetime.now(timezone.utc).isoformat(), legacyProfile=str(legacy), rustProfile=str(profile), legacyChatsImported=0, providers=sorted(credentials), state=written))
    print(json.dumps({'profile': str(profile), 'data': str(data), 'providers': sorted(credentials), 'chat_import': False, 'default_changed': False}, indent=2))


if __name__ == '__main__':
    main()
