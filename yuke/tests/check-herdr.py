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
import { client, fs } from "yuke";
import { quit } from "yuke:ui";
import { currentPane } from "yuke:session";
export default async function(ctx) {
  const tui = ctx.get("tui");
  if (!tui) return;
  const marker = ctx.root + "/generation.json";
  const generation = await fs.stat(marker) ? JSON.parse(await fs.readFile(marker)) + 1 : 1;
  tui.keymap.add({ "ctrl+g": "reload", "ctrl+q": () => quit(), "ctrl+b": () => {
    ctx.interaction.confirm("Herdr regression approval").catch(error => ctx.print(String(error)));
  } });
  ctx.once("ui.started", async () => {
    const pane = currentPane();
    const catalog = await client.catalogList(null);
    if (!pane.session.sessionId) pane.session.setModel(catalog.models.find(model => model.provider === "fixture"), "");
    const session = pane.session.sessionId || await pane.session.startChat(null, pane.composer);
    await fs.writeFile(ctx.root + "/session.json", JSON.stringify(session));
    await fs.writeFile(marker, JSON.stringify(generation));
    ctx.print("HERDR_UI_READY", generation);
  });
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=Path(shutil.which('yuke') or 'yuke'))
    parser.add_argument('--clarify', type=Path, default=Path(__file__).resolve().parents[1] / '.config/yuke/plugins/yuke-clarify')
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
    source = Path(__file__).resolve().parents[1] / '.config/yuke/plugins'
    shutil.copytree(args.clarify.resolve(strict=True), profile / 'yuke-clarify')
    (profile / 'plugins').mkdir()
    shutil.copy2(source / 'yuke-clarify-store.py', profile / 'plugins/yuke-clarify-store.py')
    (profile / 'providers.json').write_text(json.dumps({'providers': [{'id': 'fixture', 'base_url': 'http://127.0.0.1:1/v1', 'endpoints': [{'protocol': 'openai_chat'}], 'models': [{'id': 'model', 'upstream_id': 'model'}]}]}))
    (profile / 'providers.json').chmod(0o600)
    probe = profile / 'probe'
    probe.mkdir()
    (probe / 'index.js').write_text(PROBE)
    (probe / 'plugin.json').write_text(json.dumps({'name': 'herdr-probe', 'extensions': {'sh.yuke': {'entry': './index.js', 'uses': ['tui']}}}))
    (profile / 'config.json').write_text(json.dumps({'plugins': ['./herdr', './yuke-clarify', './probe']}))
    config = root / 'config/herdr'
    config.mkdir()
    (config / 'config.toml').write_text('[session]\nresume_agents_on_restore = false\n[ui.toast]\ndelivery = "herdr"\ndelay_seconds = 0\n[ui.sound]\nenabled = false\n')
    env = {'HOME': str(root / 'home'), 'PATH': os.environ['PATH'], 'SHELL': '/bin/sh', 'TERM': 'xterm-256color', 'YUKE_APPNAME': 'yuke'}
    for name in ('config', 'data', 'state', 'cache'):
        env['XDG_' + name.upper() + '_HOME'] = str(root / name)
    session = 'agent-tests-yuke-' + uuid.uuid4().hex[:8]
    address = None
    pane_id = None
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

    def client_screen():
        return mux('capture-pane', '-p', '-t', 'notifications').stdout

    def key(value):
        return cli('pane', 'send-keys', pane_id, value)

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

    def store(action, params=None):
        database = root / 'state/yuke/clarify/questions.sqlite3'
        return json.loads(run(['python3', str(profile / 'plugins/yuke-clarify-store.py'), str(database), action, json.dumps(params or {})]).stdout)

    def state():
        return api('pane.get', {'pane_id': pane_id})['pane']['agent_status']

    def capture(label):
        captures.append(label + '\n' + cli('pane', 'read', pane_id, '--source', 'visible').stdout)

    def terminal(extra=None):
        command = shlex.join(['env', '-i', *(f'{key}={value}' for key, value in {**env, **report_env, **(extra or {})}.items()), str(binary)])
        wait(lambda: any(process['name'] in ('sh', 'bash', 'zsh') for process in api('pane.process_info', {'pane_id': pane_id})['process_info']['foreground_processes']), 'private pane shell not ready')
        cli('pane', 'run', pane_id, command)

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
        key('ctrl+b')
        wait(lambda: api('pane.get', {'pane_id': pane_id})['pane']['agent_status'] == 'blocked', 'approval did not report blocked')
        capture('approval reported blocked')
        key('esc')
        wait(lambda: api('pane.get', {'pane_id': pane_id})['pane']['agent_status'] in ('idle', 'done'), 'approval dismissal did not report idle')
        print('PASS approval reports blocked then idle', flush=True)
        session_id = json.loads((probe / 'session.json').read_text())
        question = {'title': 'Herdr question', 'question': 'Which target?', 'context': '', 'options': []}
        store('add', {'session': 'foreign', 'site': 'foreign:1:1', 'question': question})
        time.sleep(2.5)
        assert state() in ('idle', 'done'), 'another session question blocked this pane: ' + str(api('pane.get', {'pane_id': pane_id}))
        api('workspace.create', {'cwd': str(root / 'work'), 'label': 'Agent Tests Notifications', 'focus': True})
        command = shlex.join(['env', '-i', *(f'{name}={value}' for name, value in env.items()), herdr, '--session', session])
        mux('new-session', '-d', '-x', '160', '-y', '40', '-s', 'notifications', '-n', 'Agent Tests Notifications', command)
        wait(lambda: 'this is a mouse-first terminal.' in client_screen(), 'private Herdr client did not draw')
        mux('send-keys', '-t', 'notifications', 'Enter')
        wait(lambda: 'this is a mouse-first terminal.' not in client_screen(), 'private Herdr welcome did not close')
        pending = store('add', {'session': session_id, 'site': 'local:1:1', 'question': question})
        wait(lambda: state() == 'blocked', 'queued clarification did not report blocked')
        wait(lambda: 'yuke needs attention' in client_screen().lower(), 'pending clarification did not show a Herdr notification')
        captures.append('Herdr question notification\n' + client_screen())
        capture('pending clarification reports blocked without opening a dialog')
        print('PASS pending question shows native Herdr notification without sound', flush=True)
        assert store('add', {'session': session_id, 'site': 'local:2:1', 'question': question})['id'] == pending['id']
        claim = store('claim', {'id': pending['id'], 'kind': 'answered', 'answer': 'local'})
        store('finish', {'id': claim['id'], 'token': claim['token'], 'input_id': 'fixture-receipt'})
        wait(lambda: state() in ('idle', 'done'), 'resolved clarification did not clear blocked')
        batch = store('add_batch', {'session': session_id, 'site': 'local:batch:1', 'questions': [
            {**question, 'question_id': 'target'}, {**question, 'title': 'Owner', 'question_id': 'owner'},
        ]})
        wait(lambda: state() == 'blocked', 'question batch did not report blocked')
        print('PASS single and batch questions report blocked with session isolation', flush=True)
        key('ctrl+g')
        wait(lambda: 'HERDR_UI_READY 2' in log(), 'native reload did not restart the private UI')
        wait(lambda: any(agent.get('agent') == 'yuke' for agent in agents()), 'native reload lost the Herdr agent')
        wait(lambda: state() == 'blocked', 'reload lost pending clarification state')
        claim = store('claim_batch', {'id': batch['id'], 'allow_unanswered': True})
        store('finish_batch', {'id': claim['id'], 'token': claim['token'], 'input_id': 'fixture-batch-receipt'})
        wait(lambda: state() in ('idle', 'done'), 'dismissed batch did not clear blocked')
        key('ctrl+b')
        wait(lambda: api('pane.get', {'pane_id': pane_id})['pane']['agent_status'] == 'blocked', 'reloaded reporter did not handle approvals')
        key('esc')
        wait(lambda: api('pane.get', {'pane_id': pane_id})['pane']['agent_status'] in ('idle', 'done'), 'reloaded reporter did not handle dismissal')
        capture('native reload registered again')
        print('PASS native reload re-registers the agent', flush=True)
        key('ctrl+q')
        wait(lambda: not agents(), 'graceful quit did not release the Herdr agent')
        print('PASS graceful quit releases the agent', flush=True)
        for flag in ('AI_AGENT', 'CLAUDECODE'):
            terminal({flag: '1'})
            generation = '3' if flag == 'AI_AGENT' else '4'
            wait(lambda: 'HERDR_UI_READY ' + generation in log(), flag + ' private UI did not start')
            assert not agents(), flag + ' nested Yuke reported over its parent'
            key('ctrl+q')
        assert '[error]' not in log() and 'Herdr report failed' not in log(), log()
        print('PASS nested agents leave parent panes unchanged', flush=True)
        (root / 'result.json').write_text(json.dumps({'startup': True, 'check_silent': True, 'headless_silent': True, 'approval_states': True, 'clarification_states': True, 'batch_states': True, 'question_session_isolation': True, 'notification': True, 'reload': True, 'quit_release': True, 'nested_silent': True}, indent=2))
    finally:
        if address and pane_id and server and server.poll() is None:
            final_pane = cli('pane', 'read', pane_id, '--source', 'visible', check=False)
            captures.append('final private Yuke pane\n' + final_pane.stdout + final_pane.stderr)
        (root / 'captures.txt').write_text('\n'.join(captures))
        screen = mux('capture-pane', '-p', '-t', 'notifications', check=False)
        (root / 'notification-screen.txt').write_text(screen.stdout + screen.stderr)
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
