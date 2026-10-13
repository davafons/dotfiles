#!/usr/bin/env python3
"""Check Yuke reporting, reload and release against a private Herdr server."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import subprocess
import tempfile
import time
import uuid

PROBE = '''
import { fs } from "yuke";
import { quit } from "yuke:ui";
export default async function(ctx) {
  const tui = ctx.get("tui");
  if (!tui) return;
  const marker = ctx.root + "/generation.json";
  const generation = await fs.stat(marker) ? JSON.parse(await fs.readFile(marker)) + 1 : 1;
  tui.keymap.add({ "ctrl+g": "reload", "ctrl+q": () => quit(), "ctrl+b": () => {
    ctx.interaction.confirm("Herdr regression approval").catch(error => ctx.print(String(error)));
  } });
  ctx.once("ui.started", async () => {
    await fs.writeFile(marker, JSON.stringify(generation));
    ctx.print("HERDR_UI_READY", generation);
  });
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=Path(shutil.which('yuke') or 'yuke'))
    parser.add_argument('--plugin', type=Path, default=Path(__file__).resolve().parents[1] / '.config/yuke/plugins/herdr')
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    herdr = shutil.which('herdr')
    tmux = shutil.which('tmux')
    assert herdr and tmux, 'herdr and tmux are required'
    root = Path(tempfile.mkdtemp(prefix='yh-', dir='/tmp')).resolve()
    root.chmod(0o700)
    print('Artifacts:', root, flush=True)
    for name in ('home', 'config', 'data', 'state', 'cache', 'work'):
        (root / name).mkdir()
    profile = root / 'config/yuke'
    profile.mkdir()
    shutil.copytree(args.plugin.resolve(strict=True), profile / 'herdr')
    probe = profile / 'probe'
    probe.mkdir()
    (probe / 'index.js').write_text(PROBE)
    (probe / 'plugin.json').write_text(json.dumps({'name': 'herdr-probe', 'extensions': {'sh.yuke': {'entry': './index.js', 'uses': ['tui']}}}))
    (profile / 'config.json').write_text(json.dumps({'plugins': ['./herdr', './probe']}))
    config = root / 'config/herdr'
    config.mkdir()
    (config / 'config.toml').write_text('[session]\nresume_agents_on_restore = false\n')
    env = {'HOME': str(root / 'home'), 'PATH': os.environ['PATH'], 'SHELL': '/bin/sh', 'TERM': 'xterm-256color', 'YUKE_APPNAME': 'yuke'}
    for name in ('config', 'data', 'state', 'cache'):
        env['XDG_' + name.upper() + '_HOME'] = str(root / name)
    session = 'agent-tests-yuke-' + uuid.uuid4().hex[:8]
    address = None
    captures = []
    server = None

    def run(argv, check=True, extra=None):
        result = subprocess.run(argv, env={**env, **(extra or {})}, cwd=root / 'work', input='', capture_output=True, text=True, timeout=15)
        if check:
            assert result.returncode == 0, result.stdout + result.stderr
        return result

    def cli(*args, check=True):
        return run([herdr, '--session', session, *args], check=check)

    def mux(*args, check=True):
        return run([tmux, '-L', session, *args], check=check)

    def api(method, params=None):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(5)
            connection.connect(str(address))
            connection.sendall((json.dumps({'id': 'yuke-regression', 'method': method, 'params': params or {}}) + '\n').encode())
            with connection.makefile('rb') as replies:
                response = json.loads(replies.readline())
        assert 'error' not in response, response
        return response['result']

    def wait(condition, label):
        end = time.monotonic() + 10
        while time.monotonic() < end:
            if condition():
                return
            time.sleep(0.05)
        raise AssertionError(label)

    def log():
        path = root / 'state/yuke/yuke.log'
        return path.read_text() if path.exists() else ''

    def agents():
        return api('agent.list')['agents']

    def capture(label):
        captures.append(label + '\n' + mux('capture-pane', '-p', '-t', 'test').stdout)

    def terminal(extra=None):
        command = shlex.join(['env', '-i', *(f'{key}={value}' for key, value in {**env, **report_env, **(extra or {})}.items()), str(binary)])
        mux('new-session', '-d', '-x', '100', '-y', '30', '-s', 'test', '-n', 'Agent Tests Yuke Herdr', '-c', str(root / 'work'), command)

    try:
        with (root / 'server.log').open('w') as output:
            server = subprocess.Popen([herdr, '--session', session, 'server'], env=env, cwd=root / 'work', stdout=output, stderr=output)
        status = ''
        def server_ready():
            nonlocal status
            status = cli('status', check=False).stdout
            return 'status: running' in status
        wait(server_ready, 'private Herdr server did not start')
        address = Path(re.search(r'socket:\s*(.+)', status).group(1).strip())
        pane = api('workspace.create', {'cwd': str(root / 'work'), 'label': 'Agent Tests Yuke Herdr', 'focus': False})['root_pane']
        pane_id = pane['pane_id']
        report_env = {'HERDR_ENV': '1', 'HERDR_PANE_ID': pane_id, 'HERDR_SOCKET_PATH': str(address)}
        terminal()
        wait(lambda: 'HERDR_UI_READY 1' in log(), 'private Yuke UI did not start')
        wait(lambda: any(agent.get('agent') == 'yuke' and agent['pane_id'] == pane_id for agent in agents()), 'interactive Yuke did not appear in Herdr agent.list')
        assert api('pane.get', {'pane_id': pane_id})['pane']['agent_status'] in ('idle', 'done')
        capture('startup registered in real Herdr')
        print('PASS startup appears in Herdr agent.list', flush=True)
        checked = run([str(binary), 'check'], extra=report_env)
        (root / 'check.log').write_text(checked.stdout + checked.stderr)
        assert any(agent.get('agent') == 'yuke' for agent in agents()), 'yuke check released its parent agent'
        print('PASS yuke check leaves the parent agent unchanged', flush=True)
        headless = run([str(binary), '--rpc'], extra=report_env)
        (root / 'rpc.log').write_text(headless.stdout + headless.stderr)
        assert any(agent.get('agent') == 'yuke' for agent in agents()), 'headless startup released its parent agent'
        print('PASS headless startup leaves the parent agent unchanged', flush=True)
        mux('send-keys', '-t', 'test', 'C-b')
        wait(lambda: api('pane.get', {'pane_id': pane_id})['pane']['agent_status'] == 'blocked', 'approval did not report blocked')
        capture('approval reported blocked')
        mux('send-keys', '-t', 'test', 'Escape')
        wait(lambda: api('pane.get', {'pane_id': pane_id})['pane']['agent_status'] in ('idle', 'done'), 'approval dismissal did not report idle')
        print('PASS approval reports blocked then idle', flush=True)
        mux('send-keys', '-t', 'test', 'C-g')
        wait(lambda: 'HERDR_UI_READY 2' in log(), 'native reload did not restart the private UI')
        wait(lambda: any(agent.get('agent') == 'yuke' for agent in agents()), 'native reload lost the Herdr agent')
        mux('send-keys', '-t', 'test', 'C-b')
        wait(lambda: api('pane.get', {'pane_id': pane_id})['pane']['agent_status'] == 'blocked', 'reloaded reporter did not handle approvals')
        mux('send-keys', '-t', 'test', 'Escape')
        wait(lambda: api('pane.get', {'pane_id': pane_id})['pane']['agent_status'] in ('idle', 'done'), 'reloaded reporter did not handle dismissal')
        capture('native reload registered again')
        print('PASS native reload re-registers the agent', flush=True)
        mux('send-keys', '-t', 'test', 'C-q')
        wait(lambda: not agents(), 'graceful quit did not release the Herdr agent')
        mux('kill-session', '-t', 'test', check=False)
        print('PASS graceful quit releases the agent', flush=True)
        for flag in ('AI_AGENT', 'CLAUDECODE'):
            terminal({flag: '1'})
            generation = '3' if flag == 'AI_AGENT' else '4'
            wait(lambda: 'HERDR_UI_READY ' + generation in log(), flag + ' private UI did not start')
            assert not agents(), flag + ' nested Yuke reported over its parent'
            mux('send-keys', '-t', 'test', 'C-q')
            mux('kill-session', '-t', 'test', check=False)
        assert '[error]' not in log() and 'Herdr report failed' not in log(), log()
        print('PASS nested agents leave parent panes unchanged', flush=True)
        (root / 'result.json').write_text(json.dumps({'startup': True, 'check_silent': True, 'headless_silent': True, 'approval_states': True, 'reload': True, 'quit_release': True, 'nested_silent': True}, indent=2))
    finally:
        (root / 'captures.txt').write_text('\n'.join(captures))
        mux('kill-server', check=False)
        if server:
            cli('server', 'stop', check=False)
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.terminate()
                server.wait(timeout=5)
        print('Herdr regression artifacts:', root, flush=True)


if __name__ == '__main__':
    main()
