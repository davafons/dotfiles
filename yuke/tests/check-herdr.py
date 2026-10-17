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
  tui.command.add("link-fixture", {desc: "Render a file reference fixture", slash: true, args: true, run: async (index) => {
    const fixture = JSON.parse(await fs.readFile(ctx.root + "/fixtures.json"))[Number(index)];
    const view = currentPane();
    const message = 100 + Number(index);
    view.transcript.partsOf = () => [fixture.part || {type: "text", id: 11, text: fixture.text}];
    view.transcript.setOutline([{id: message, type: "assistant"}], null);
    tui.root.invalidate();
    setTimeout(async () => {
      const header = fixture.part && view.transcript.partHeader(message, fixture.part.id);
      const text = header ? view.transcript.rowTextAt(message, header.row) : "";
      const column = text.indexOf(fixture.label);
      const position = header ? {...header, col: column + 1} : view.transcript.posAtSource(message, fixture.at);
      const screen = view.transcript.screenAt(position);
      await fs.writeFile(ctx.root + "/click.json", JSON.stringify({index: Number(index), screen,
        anchor: view.transcript.anchorAt(position), hit: view.transcript.partAt(position),
        headerText: text, column, rows: view.transcript.rowCountOf(message)}));
    }, 150);
  }});
  const marker = ctx.root + "/generation.json";
  const generation = await fs.stat(marker) ? JSON.parse(await fs.readFile(marker)) + 1 : 1;
  const fileRequests = [];
  ctx.on("vim-mode:open-file", (_view, position) => fileRequests.push(position));
  tui.keymap.add({ "f12": () => {
    const view = currentPane();
    void fs.writeFile(ctx.root + "/cursor.json", JSON.stringify({caret: view.transcript.caret,
      selected: view.transcript.selectedText(), selection: view.transcript.selection,
      focus: view.focus, draft: view.composer.text, fileRequests: fileRequests.length,
      rows: view.transcript.messageCount() ? view.transcript.rowCountOf(view.transcript.messageIdAt(0)) : 0}));
  }, "ctrl+f": () => {
    const view = currentPane();
    view.focusRegion("composer");
    ctx.get("composer-vim")?.setMode(view.composer, "insert");
  }, "ctrl+g": "reload", "ctrl+q": () => quit(), "ctrl+b": () => {
    ctx.interaction.confirm("Herdr regression approval").catch(error => ctx.print(String(error)));
  } });
  ctx.once("ui.started", async () => {
    await fs.writeFile(ctx.root + "/commands.json", JSON.stringify(tui.command.list()));
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


def code_checks(root, probe, api, cli, key, wait, run, captures):
    work = root / 'work'
    first = work / 'sample file.txt'
    first.write_text('first line\nsecond line\nthird line\n')
    second = work / "quote'|file.txt"
    second.write_text('safe file content\nsecond line\nthird line\n')
    nested = work / 'nested/inside/sample.txt'
    nested.parent.mkdir(parents=True)
    nested.write_text('nested first\nnested second\n')
    fixtures = [
        {'text': '[Review the sample](sample%20file.txt#L2)', 'at': 4},
        {'text': "`quote'|file.txt:1:4`", 'at': 5},
        {'text': 'sample file is not a link.\n[Web](https://example.com/sample.txt)', 'at': 31},
        {'text': 'See `missing.txt` for the next step.', 'at': 7},
        {'text': 'sample%20file.txt is not decoded outside a URL.', 'at': 4},
        {'text': '[A deliberately long label ' + 'review this source file across wrapped rows ' * 6 + 'ends here](sample%20file.txt#L3)', 'at': 145},
        {'text': '`sample file.txt:2:3`', 'at': 6},
        {'part': {'type': 'tool', 'id': 11, 'name': 'edit', 'arguments': json.dumps({'path': 'sample file.txt', 'old_string': 'first', 'new_string': 'after'}),
                  'state': {'type': 'completed', 'output': '\n'.join('tool output line ' + str(n) for n in range(20)), 'duration_ms': 100}}, 'label': 'sample file.txt'},
        {'part': {'type': 'tool', 'id': 11, 'name': 'read', 'arguments': json.dumps({'path': str(second), 'start': 2}),
                  'state': {'type': 'completed', 'output': 'safe file content\n', 'duration_ms': 100}}, 'label': second.name},
        {'part': {'type': 'tool', 'id': 11, 'name': 'write', 'arguments': json.dumps({'path': 'sample file.txt', 'content': 'not written'}),
                  'state': {'type': 'completed', 'output': 'File saved', 'duration_ms': 100}}, 'label': 'sample file.txt'},
        {'part': {'type': 'tool', 'id': 11, 'name': 'exec', 'arguments': json.dumps({'command': 'echo sample file.txt', 'path': 'sample file.txt'}),
                  'state': {'type': 'completed', 'output': 'not a file link', 'duration_ms': 100}}, 'label': 'sample file.txt'},
        {'text': '`nested/inside/sample.txt:2`', 'at': 5},
        {'text': '`sample file.txt:3:2`', 'at': 6},
    ]
    (probe / 'fixtures.json').write_text(json.dumps(fixtures))
    pane_id = api('agent.list')['agents'][0]['pane_id']
    nvim = shutil.which('nvim')

    def lua(record, body):
        expression = 'luaeval(' + json.dumps('(function() ' + body + ' end)()') + ')'
        return run([nvim, '--headless', '--server', record['nvim_socket'], '--remote-expr', expression]).stdout.strip()

    def revealed(current, path):
        wait(lambda: lua(current, "local api=require('nvim-tree.api'); local node=api.tree.get_node_under_cursor(); return api.tree.is_visible() and node and node.absolute_path or ''") == str(path), 'opened file highlighted in tree: ' + path.name)
        assert lua(current, 'return vim.api.nvim_buf_get_name(0)') == str(path), 'tree reveal stole focus from the opened file'

    def record():
        found = list((root / 'state/herdr/plugins/david.code').glob('code-*.json'))
        if not found:
            return None
        return json.loads(found[0].read_text())

    def draw(index):
        key('ctrl+f')
        cli('pane', 'send-text', pane_id, '/link-fixture ' + str(index))
        key('enter')
        path = probe / 'click.json'
        wait(lambda: path.exists() and json.loads(path.read_text())['index'] == index, 'fixture draw ' + str(index))
        rendered = json.loads(path.read_text())
        assert rendered['screen'], rendered
        if index == 5:
            assert rendered['screen']['y'] > 0, 'long label did not actually wrap'
        captures.append('file fixture ' + str(index) + '\n' + cli('pane', 'read', pane_id, '--source', 'visible').stdout)
        return rendered['screen']

    def click(index):
        point = draw(index)
        cli('pane', 'send-text', pane_id, f"\x1b[<0;{point['x'] + 1};{point['y'] + 1}M\x1b[<0;{point['x'] + 1};{point['y'] + 1}m")

    def cursor():
        path = probe / 'cursor.json'
        path.unlink(missing_ok=True)
        key('f12')
        wait(path.exists, 'transcript cursor snapshot')
        return json.loads(path.read_text())

    def returned(current):
        lua(current, "require('herdr-code').return_to_agent(); return true")
        wait(lambda: api('session.snapshot')['snapshot']['focused_pane_id'] == pane_id, 'return to Yuke')

    click(0)
    wait(lambda: record() and api('session.snapshot')['snapshot']['focused_pane_id'] == record()['editor_pane'], 'Markdown click opens Code')
    current = record()
    wait(lambda: lua(current, 'return vim.api.nvim_buf_get_name(0)') == str(first), 'linked file buffer')
    assert lua(current, 'return vim.json.encode(vim.api.nvim_win_get_cursor(0))') == '[2,0]'
    assert lua(current, "return require('nvim-tree.api').tree.is_visible()") == 'true'
    revealed(current, first)
    lua(current, "vim.api.nvim_buf_set_lines(0,0,1,false,{'unsaved review text'}); require('herdr-nvim.annotations').add(0,0,0,'Keep this tag'); require('nvim-tree.api').tree.close(); return true")
    returned(current)
    click(1)
    wait(lambda: lua(current, 'return vim.api.nvim_buf_get_name(0)') == str(second), 'quoted filename opens without executing a command')
    revealed(current, second)
    assert lua(current, 'return vim.json.encode(vim.api.nvim_win_get_cursor(0))') == '[1,3]'
    assert record()['editor_pane'] == current['editor_pane']
    assert len(api('pane.list')['panes']) == 2
    returned(current)
    for index in (2, 3, 4):
        click(index)
        time.sleep(.3)
        assert api('session.snapshot')['snapshot']['focused_pane_id'] == pane_id, 'nonlocal or absent reference stole focus'
        assert len(api('pane.list')['panes']) == 2
    click(12)
    wait(lambda: lua(current, 'return vim.api.nvim_buf_get_name(0)') == str(first), 'file-location click opens modified buffer')
    assert lua(current, 'return vim.json.encode(vim.api.nvim_win_get_cursor(0))') == '[3,1]'
    assert lua(current, 'return vim.api.nvim_buf_get_lines(0,0,1,false)[1]') == 'unsaved review text'
    assert lua(current, 'return vim.bo.modified') == 'true'
    assert lua(current, "return require('herdr-nvim.annotations').total()") == '1'
    assert first.read_text() == 'first line\nsecond line\nthird line\n'
    returned(current)
    click(5)
    wait(lambda: api('session.snapshot')['snapshot']['focused_pane_id'] == current['editor_pane'], 'wrapped label opens Code')
    assert lua(current, 'return vim.json.encode(vim.api.nvim_win_get_cursor(0))') == '[3,0]'
    returned(current)
    key('ctrl+g')
    wait(lambda: 'HERDR_UI_READY 2' in (root / 'state/yuke/yuke.log').read_text(), 'reload file-link listener')
    click(6)
    wait(lambda: api('session.snapshot')['snapshot']['focused_pane_id'] == current['editor_pane'], 'click after reload')
    assert lua(current, 'return vim.json.encode(vim.api.nvim_win_get_cursor(0))') == '[2,2]'
    assert record()['editor_pane'] == current['editor_pane']
    captures.append('real Code file\n' + cli('pane', 'read', current['editor_pane'], '--source', 'visible').stdout)
    returned(current)
    draw(0)
    key('tab')
    cli('pane', 'send-text', pane_id, 'ggg')
    time.sleep(.15)
    assert api('session.snapshot')['snapshot']['focused_pane_id'] == pane_id, 'g prefix opened a file before f'
    key('f')
    wait(lambda: api('session.snapshot')['snapshot']['focused_pane_id'] == current['editor_pane'], 'gf opens Markdown link under transcript cursor')
    assert lua(current, 'return vim.json.encode(vim.api.nvim_win_get_cursor(0))') == '[2,0]'
    returned(current)
    assert cursor()['fileRequests'] == 1, 'reload left duplicate gf producers'
    cli('pane', 'send-text', pane_id, 'ggvlgf')
    visual = cursor()
    assert visual['selection'] and visual['fileRequests'] == 1, 'visual gf must not dispatch file opening'
    key('o')
    swapped = cursor()
    assert swapped['selection']['cursor'] == visual['selection']['anchor'], 'visual o no longer swaps selection ends'
    key('esc')
    cli('pane', 'send-text', pane_id, 'ygf')
    assert cursor()['fileRequests'] == 1, 'operator gf dispatched file opening'
    key('tab')
    cli('pane', 'send-text', pane_id, 'gf')
    composer = cursor()
    assert composer['draft'] == 'gf' and composer['fileRequests'] == 1, 'composer text must not open a file'
    key('ctrl+u')
    draw(1)
    key('tab')
    cli('pane', 'send-text', pane_id, 'gggf')
    wait(lambda: lua(current, 'return vim.api.nvim_buf_get_name(0)') == str(second), 'gf opens inline path under transcript cursor')
    assert lua(current, 'return vim.json.encode(vim.api.nvim_win_get_cursor(0))') == '[1,3]'
    returned(current)
    draw(2)
    key('tab')
    cli('pane', 'send-text', pane_id, 'gggf')
    assert cursor()['fileRequests'] == 3
    assert api('session.snapshot')['snapshot']['focused_pane_id'] == pane_id, 'gf on ordinary text must not change focus'
    draw(5)
    key('tab')
    cli('pane', 'send-text', pane_id, 'ggjgf')
    wait(lambda: api('session.snapshot')['snapshot']['focused_pane_id'] == current['editor_pane'], 'gf opens wrapped Markdown label')
    assert lua(current, 'return vim.json.encode(vim.api.nvim_win_get_cursor(0))') == '[3,0]'
    returned(current)
    click(7)
    wait(lambda: api('session.snapshot')['snapshot']['focused_pane_id'] == current['editor_pane'], 'click on edit tool filename opens Code')
    assert lua(current, 'return vim.api.nvim_buf_get_name(0)') == str(first)
    header = json.loads((probe / 'click.json').read_text())
    assert header['anchor']['kind'] == 'header' and header['hit']['row']['header'], header
    returned(current)
    assert cursor()['rows'] == header['rows'], 'file click also toggled the tool fold'
    point = header['screen']
    verb_x = point['x'] - header['column']
    cli('pane', 'send-text', pane_id, f"\x1b[<0;{verb_x + 1};{point['y'] + 1}M\x1b[<0;{verb_x + 1};{point['y'] + 1}m")
    assert api('session.snapshot')['snapshot']['focused_pane_id'] == pane_id, 'click on edit verb opened the file'
    wait(lambda: cursor()['rows'] != header['rows'], 'click on tool verb still folds output')
    timing_x = point['x'] - header['anchor']['col'] + len(header['headerText']) - 2
    cli('pane', 'send-text', pane_id, f"\x1b[<0;{timing_x + 1};{point['y'] + 1}M\x1b[<0;{timing_x + 1};{point['y'] + 1}m")
    wait(lambda: cursor()['rows'] == header['rows'], 'click on tool timing still folds output')
    assert api('session.snapshot')['snapshot']['focused_pane_id'] == pane_id
    draw(8)
    key('tab')
    cli('pane', 'send-text', pane_id, 'ggwgf')
    wait(lambda: api('session.snapshot')['snapshot']['focused_pane_id'] == current['editor_pane'], 'gf opens read tool filename')
    assert lua(current, 'return vim.api.nvim_buf_get_name(0)') == str(second)
    assert lua(current, 'return vim.json.encode(vim.api.nvim_win_get_cursor(0))') == '[2,0]'
    returned(current)
    click(9)
    wait(lambda: api('session.snapshot')['snapshot']['focused_pane_id'] == current['editor_pane'], 'click opens write tool filename')
    assert lua(current, 'return vim.api.nvim_buf_get_name(0)') == str(first)
    assert lua(current, 'return vim.api.nvim_buf_get_lines(0,0,1,false)[1]') == 'unsaved review text'
    assert first.read_text() == 'first line\nsecond line\nthird line\n'
    returned(current)
    click(10)
    assert api('session.snapshot')['snapshot']['focused_pane_id'] == pane_id, 'exec heading must not treat command text as a file'
    print('PASS read/edit/write tool heading click/gf and filename-only fold isolation', flush=True)
    click(11)
    wait(lambda: api('session.snapshot')['snapshot']['focused_pane_id'] == current['editor_pane'], 'nested file opens Code')
    revealed(current, nested)
    assert lua(current, 'return vim.json.encode(vim.api.nvim_win_get_cursor(0))') == '[2,0]'
    assert lua(current, 'return vim.fn.getcwd()') == str(work)
    returned(current)
    print('PASS chat-opened files reveal in tree with editor focus, hidden-tree reopening and nested parents', flush=True)
    destination = root / 'other-checkout'
    run(['jj', 'git', 'init', str(destination)])
    other_file = destination / 'sample file.txt'
    other_file.write_text('other checkout\n')
    api('plugin.action.invoke', {'plugin_id': 'david.code', 'action_id': 'open-file', 'context': {
        'invocation_source': 'yuke', 'focused_pane_id': pane_id, 'focused_pane_cwd': str(destination), 'clicked_url': other_file.as_uri()}})
    def other_record():
        for path in (root / 'state/herdr/plugins/david.code').glob('code-*.json'):
            saved = json.loads(path.read_text())
            if saved['root'] == str(destination) and saved.get('editor_pane'):
                return saved
        return None
    wait(lambda: other_record() and api('session.snapshot')['snapshot']['focused_pane_id'] == other_record()['editor_pane'], 'workspace override selects its own checkout editor')
    independent = other_record()
    assert independent['editor_pane'] != current['editor_pane']
    assert lua(independent, 'return vim.api.nvim_buf_get_name(0)') == str(other_file)
    assert lua(current, 'return vim.api.nvim_buf_get_lines(vim.fn.bufnr(' + json.dumps(str(first)) + '),0,1,false)[1]') == 'unsaved review text'
    assert lua(current, "return require('herdr-nvim.annotations').total()") == '1'
    returned(independent)
    key('ctrl+q')
    wait(lambda: not api('agent.list')['agents'], 'Yuke quit releases reporter')
    (root / 'code-result.json').write_text(json.dumps({'markdown_click': True, 'inline_location': True,
        'wrapped_label': True, 'quoted_path': True, 'no_code_command': True, 'web_untouched': True,
        'missing_untouched': True, 'shared_editor': True, 'unsaved_and_tags_kept': True, 'reload': True,
        'workspace_override': True, 'checkout_isolation': True, 'normal_gf': True,
        'visual_o_and_operator_gates': True, 'composer_text_unchanged': True, 'wrapped_gf': True,
        'file_tool_headings': True, 'filename_only_fold_isolation': True, 'read_start_line': True,
        'tree_reveal': True, 'editor_focus': True, 'hidden_tree_reopened': True, 'nested_parents_revealed': True}, indent=2))
    print('PASS native mouse and Vim gf, exact cursor, shared Code, unsaved buffers/tags, mode gates, checkout isolation and reload', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=Path(shutil.which('yuke') or 'yuke'))
    parser.add_argument('--clarify', type=Path, default=Path(__file__).resolve().parents[1] / '.config/yuke/plugins/yuke-clarify')
    parser.add_argument('--plugin', type=Path, default=Path(__file__).resolve().parents[1] / '.config/yuke/plugins/herdr')
    parser.add_argument('--code', action='store_true', help='Drive file links through the real shared Neovim editor')
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
    (probe / 'plugin.json').write_text(json.dumps({'name': 'herdr-probe', 'extensions': {'sh.yuke': {'entry': './index.js', 'uses': ['tui', 'composer-vim']}}}))
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
        launcher = root / 'launch-yuke.sh'
        launcher.write_text('#!/bin/sh\nexec ' + command + '\n')
        cli('pane', 'run', pane_id, shlex.join(['/bin/sh', str(launcher)]))

    if args.code:
        shutil.copytree(source / 'vim-mode', profile / 'vim-mode')
        (profile / 'config.json').write_text(json.dumps({'plugins': ['./vim-mode', './herdr', './yuke-clarify', './probe']}))
        dotfiles = Path(__file__).resolve().parents[2]
        runtime = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'nvim/personal'
        assert shutil.which('nvim') and (runtime / 'lazy/herdr-nvim').exists(), 'Installed Neovim plugins are required'
        (root / 'config/nvim').symlink_to(dotfiles / 'nvim/.config/nvim', target_is_directory=True)
        (root / 'data/nvim').mkdir()
        (root / 'data/nvim/personal').symlink_to(runtime, target_is_directory=True)
        candidate = config / 'code'
        shutil.copytree(dotfiles / 'herdr/.config/herdr/local-plugins/code', candidate,
                        ignore=shutil.ignore_patterns('__pycache__'))
        cli('plugin', 'link', str(candidate), '--enabled')
        run(['jj', 'git', 'init', str(root / 'work')])

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
        commands = json.loads((probe / 'commands.json').read_text())
        assert not any(row['name'] == 'herdr:code' or row['slash'] == 'code' for row in commands), 'Redundant /code command is still registered'
        if args.code:
            code_checks(root, probe, api, cli, key, wait, run, captures)
            return
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
        owned_pids = []
        for path in (root / 'state/herdr/plugins/david.code').glob('code-*.json'):
            saved = json.loads(path.read_text())
            owned_pids.extend(saved[field] for field in ('daemon_pid', 'host_pid') if saved.get(field))
        mux('kill-server', check=False)
        if server:
            cli('server', 'stop', check=False)
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.terminate()
                server.wait(timeout=5)
        def stopped():
            for pid in owned_pids:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    continue
                return False
            return True
        wait(stopped, 'owned Code processes stopped')
        (root / 'cleanup.json').write_text(json.dumps({'server_stopped': server is None or server.poll() is not None,
                                                       'owned_code_pids': owned_pids, 'code_stopped': stopped()}))
        print('Herdr regression artifacts:', root, flush=True)


if __name__ == '__main__':
    main()
