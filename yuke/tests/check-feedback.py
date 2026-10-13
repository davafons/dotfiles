#!/usr/bin/env python3
"""Drive live grouped feedback through a local provider, tool and detached terminal."""
import argparse
import http.server
import json
import os
import re
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=Path(shutil.which('yuke') or 'yuke'))
    parser.add_argument('--with-vim', action='store_true')
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    source = Path(__file__).resolve().parents[1] / '.config/yuke'
    root = Path(tempfile.mkdtemp(prefix='feedback-', dir='/tmp')).resolve()
    root.chmod(0o700)
    print('Artifacts:', root, flush=True)
    profile = root / 'config/yuke'
    profile.mkdir(parents=True)
    shutil.copytree(source / 'plugins/run-feedback', profile / 'feedback')
    if args.with_vim:
        shutil.copytree(source / 'plugins/vim-mode', profile / 'vim')
    (root / 'config/lib').mkdir()
    shutil.copyfile(source / 'lib/settings.js', root / 'config/lib/settings.js')
    for name in ['home', 'work', 'data', 'state', 'cache']:
        (root / name).mkdir()
    probe = profile / 'probe'
    probe.mkdir()
    (probe / 'plugin.json').write_text(json.dumps({'name': 'feedback-probe', 'extensions': {'sh.yuke': {'entry': './index.js', 'uses': ['tui', 'composer-vim']}}}))
    (probe / 'index.js').write_text('''
import { client, events, fs } from "yuke";
import { currentPane, showSession } from "yuke:session";
export default function(ctx) {
  ctx.tools.define({ name: "fixture_tool", description: "Local test fixture", parameters: { type: "object", properties: {}, additionalProperties: false },
    async execute() { await new Promise(done => setTimeout(done, 450)); return "fixture tool completed"; }
  });
  const tui = ctx.get("tui");
  for (const name of ["sessionParts", "sessionPart", "partTextPage"]) ctx.advise(client, name, "before", (_session, id) => {
    if (id < 0) throw Error("display-only ID reached native reader " + name);
  });
  let originalId = null;
  let snapshot = 0;
  const clocks = [];
  ctx.advise(Object.getPrototypeOf(tui), "tickable", "before", function(clock) { clocks.push(clock); });
  tui.keymap.add({
    "ctrl+t": () => ctx.print("FEEDBACK_CLOCK", clocks.length, clocks[0]?.needsTick()),
    "f8": async () => {
      const pane = currentPane(), id = pane.session.sessionId;
      const outline = client.sessionOutline(id);
      const shown = pane.transcript.messages().map(message => ({ ...message,
        rows: Array.from({ length: pane.transcript.rowCountOf(message.id) }, (_, row) => pane.transcript.rowTextAt(message.id, row))
      }));
      await fs.writeFile(ctx.root + "/snapshot-" + (++snapshot) + ".json", JSON.stringify({ outline, shown, strip: events.bail("chat.strip", pane), queue: await client.sessionQueue(id) }));
      ctx.print("FEEDBACK_SNAPSHOT", snapshot);
    },
    "f6": async () => {
      const id = currentPane().session.sessionId;
      await client.sessionSendInput(id, client.textContent("QUEUED_FIXTURE"));
      ctx.print("FEEDBACK_QUEUED");
    },
    "f7": async () => {
      const id = currentPane().session.sessionId;
      for (const item of (await client.sessionQueue(id)).items) await client.sessionCancelInput(id, item.input_id);
      ctx.print("FEEDBACK_QUEUE_CLEARED");
    },
    "f4": () => {
      const transcript = currentPane().transcript;
      const card = transcript.messages().find(message => message.id < 0);
      if (card) transcript.activate({ id: card.id, row: 0, col: 0 });
    },
    "f9": async () => {
      const saved = await client.sessionCreate({ workspace_path: (await fs.stat(".")).path, model: "feedback-test/model", reasoning: "high" });
      showSession(currentPane(), saved.session.id);
      ctx.print("FEEDBACK_OTHER_SESSION");
    },
    "f10": () => { showSession(currentPane(), originalId); ctx.print("FEEDBACK_ORIGINAL_SESSION"); },
    "ctrl+g": "reload",
  });
  ctx.once("ui.started", async () => {
    if (!currentPane().session.sessionId) {
      const session = await client.sessionCreate({ workspace_path: (await fs.stat(".")).path, model: "feedback-test/model", reasoning: "high" });
      showSession(currentPane(), session.session.id);
    }
    originalId = currentPane().session.sessionId;
    ctx.get("composer-vim")?.setMode(currentPane().composer, "insert");
    ctx.print("FEEDBACK_READY");
  });
}
''')
    (profile / 'config.json').write_text(json.dumps({'plugins': (['./vim'] if args.with_vim else []) + ['./probe', './feedback']}))
    requests = []

    class Provider(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            time.sleep(1.0)
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()

            def chunk(delta, finish=None, usage=None):
                body = {'id': 'fixture', 'object': 'chat.completion.chunk', 'created': 1, 'model': 'model', 'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}]}
                if usage:
                    body['usage'] = usage
                self.wfile.write(('data: ' + json.dumps(body) + '\n\n').encode())
                self.wfile.flush()

            time.sleep(0.5)
            chunk({'role': 'assistant', 'reasoning_content': 'Fixture reasoning'})
            time.sleep(0.5)
            chunk({'reasoning_content': ' with visible duration.'})
            time.sleep(0.5)
            if len(requests) == 1:
                chunk({'tool_calls': [{'index': 0, 'id': 'fixture-call', 'type': 'function', 'function': {'name': 'fixture_tool', 'arguments': '{}'}}]})
                chunk({}, 'tool_calls', {'prompt_tokens': 10, 'completion_tokens': 8, 'total_tokens': 18})
            else:
                chunk({'content': 'FEEDBACK_'})
                time.sleep(0.5)
                chunk({'content': 'COMPLETE'})
                time.sleep(0.4)
                chunk({}, 'stop', {'prompt_tokens': 20, 'completion_tokens': 12, 'total_tokens': 32})
            self.wfile.write(b'data: [DONE]\n\n')
            self.wfile.flush()

    provider = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    (profile / 'providers.json').write_text(json.dumps({'providers': [{'id': 'feedback-test', 'base_url': f'http://127.0.0.1:{provider.server_port}/v1', 'api_key': 'fixture-only', 'endpoints': [{'protocol': 'openai_chat', 'credential_header': 'authorization_bearer'}], 'models': [{'id': 'model', 'upstream_id': 'model', 'reasoning_levels': ['high'], 'flags': {'supports_tools': True, 'thinking_format': 'openai'}, 'limits': {'context_window': 100000, 'max_output_tokens': 4096}}]}]}))
    (profile / 'providers.json').chmod(0o600)
    env = {'PATH': os.environ['PATH'], 'HOME': str(root / 'home'), 'TERM': 'xterm-256color', 'YUKE_APPNAME': 'yuke'}
    for name in ['config', 'state', 'data', 'cache']:
        env['XDG_' + name.upper() + '_HOME'] = str(root / name)
    mux_socket = 'feedback-' + uuid.uuid4().hex[:10]
    captures = []

    def mux(*args):
        return subprocess.check_output(['tmux', '-L', mux_socket, *args], text=True)

    def screen():
        return mux('capture-pane', '-p', '-t', 'test')

    def logs():
        return '\n'.join(path.read_text() for path in (root / 'state').rglob('*.log'))

    def wait(condition, label):
        end = time.monotonic() + 15
        while time.monotonic() < end:
            if condition():
                captures.append(label + '\n' + screen())
                return
            time.sleep(0.03)
        raise AssertionError(label + '\n' + screen() + '\n' + logs())

    try:
        command = shlex.join(['env', '-i', *(f'{key}={value}' for key, value in env.items()), str(binary)])
        mux('new-session', '-d', '-x', '120', '-y', '40', '-s', 'test', '-n', 'Agent Tests run feedback', '-c', str(root / 'work'), command)
        wait(lambda: 'FEEDBACK_READY' in logs(), 'private session ready')
        mux('send-keys', '-t', 'test', '-l', 'Run the local feedback fixture.')
        mux('send-keys', '-t', 'test', 'Enter')
        wait(lambda: 'waiting for model' in screen(), 'native waiting phase')
        mux('send-keys', '-t', 'test', 'F6')
        wait(lambda: 'FEEDBACK_QUEUED' in logs() and 'QUEUED_FIXTURE' in screen(), 'queued input still appears above the prompt')
        queued = screen().splitlines()
        phase_row = next(i for i, row in enumerate(queued) if 'waiting for model' in row)
        queue_row = next(i for i, row in enumerate(queued) if 'QUEUED_FIXTURE' in row)
        assert phase_row < queue_row - 2, screen()
        mux('send-keys', '-t', 'test', 'F7')
        wait(lambda: 'FEEDBACK_QUEUE_CLEARED' in logs(), 'fixture queue removed before delivery')
        wait(lambda: 'thinking' in screen() and 'reasoning' in screen() and '~' in screen() and 'tok/s' in screen(), 'live reasoning duration and estimated token speed')
        def thinking_time():
            match = re.search(r'thinking[^\n]* · (\d+\.\d+)s', screen())
            return float(match.group(1)) if match else -1
        first = thinking_time()
        assert first >= 0, screen()
        wait(lambda: thinking_time() > first, 'reasoning clock advances while streaming')
        mux('send-keys', '-t', 'test', 'C-t')
        wait(lambda: 'FEEDBACK_CLOCK 1 {"periodMs":100}' in logs(), 'one active feedback clock')
        wait(lambda: 'fixture tool completed' in screen(), 'real local tool result')
        wait(lambda: 'FEEDBACK_' in screen() and 'FEEDBACK_COMPLETE' not in screen() and 'receiving response' in screen(), 'partial answer displays before the next response chunk')
        wait(lambda: 'FEEDBACK_COMPLETE' in screen() and 'thought' in screen(), 'completed reasoning and assistant response')
        time.sleep(0.5)
        mux('send-keys', '-t', 'test', 'F8')
        wait(lambda: (probe / 'snapshot-1.json').exists(), 'display-only outline snapshot')
        saved = json.loads((probe / 'snapshot-1.json').read_text())
        native = saved['outline']['messages']
        shown = saved['shown']
        assert [row['id'] for row in shown if row['id'] >= 0] == [row['id'] for row in native], saved
        cards = [row for row in shown if row['id'] < 0]
        assert len(cards) == 2, saved
        assert all(len([text for text in card['rows'] if text]) == 1 and re.match(r'◷ model request · \d+\.\d+s$', card['rows'][0]) for card in cards), saved
        assert not any('→ ' in text for card in cards for text in card['rows']), saved
        assert saved['queue']['items'] == [], saved
        assert not any('waiting for model' in row['text'] for row in saved.get('strip') or []), saved
        assert shown[0]['type'] == 'user' and shown[1]['id'] < 0 and shown[2]['type'] == 'assistant' and shown[3]['id'] < 0, saved
        frozen = [card['rows'] for card in cards]
        mux('send-keys', '-t', 'test', 'C-o')
        wait(lambda: 'waiting for model' in screen(), 'Ctrl+O expands the timing breakdown')
        mux('send-keys', '-t', 'test', 'F8')
        wait(lambda: (probe / 'snapshot-2.json').exists(), 'expanded phase snapshot')
        expanded = json.loads((probe / 'snapshot-2.json').read_text())
        expanded_cards = [row for row in expanded['shown'] if row['id'] < 0]
        assert all(any('waiting for model' in text for text in card['rows']) for card in expanded_cards), expanded
        assert all(any('receiving response' in text for text in card['rows']) for card in expanded_cards), expanded
        assert all(card['rows'][0] == cards[i]['rows'][0] for i, card in enumerate(expanded_cards)), expanded
        mux('send-keys', '-t', 'test', 'C-o')
        wait(lambda: 'waiting for model' not in screen(), 'Ctrl+O folds the timing breakdown')
        time.sleep(0.3)
        mux('send-keys', '-t', 'test', 'F8')
        wait(lambda: (probe / 'snapshot-3.json').exists(), 'idle phase clocks stay frozen after a fold')
        assert [row['rows'] for row in json.loads((probe / 'snapshot-3.json').read_text())['shown'] if row['id'] < 0] == frozen
        mux('send-keys', '-t', 'test', 'F4')
        wait(lambda: screen().count('waiting for model') == 1, 'activating one heading expands only that timing block')
        mux('send-keys', '-t', 'test', 'F4')
        wait(lambda: 'waiting for model' not in screen(), 'activating the heading folds it again')
        mux('resize-window', '-t', 'test', '-x', '35', '-y', '40')
        wait(lambda: 'FEEDBACK_COMPLETE' in screen(), 'narrow transcript remains readable')
        time.sleep(0.2)
        assert all(len(row) <= 35 for row in screen().splitlines()), screen()
        mux('resize-window', '-t', 'test', '-x', '120', '-y', '40')
        mux('send-keys', '-t', 'test', 'C-t')
        wait(lambda: 'FEEDBACK_CLOCK 1 null' in logs(), 'feedback clock stops when idle')
        before = logs().count('FEEDBACK_READY')
        mux('send-keys', '-t', 'test', 'C-g')
        wait(lambda: logs().count('FEEDBACK_READY') > before, 'native reload reattaches feedback')
        mux('send-keys', '-t', 'test', 'C-t')
        wait(lambda: logs().count('FEEDBACK_CLOCK 1 null') == 2, 'one idle feedback clock after reload')
        mux('send-keys', '-t', 'test', 'F8')
        wait(lambda: (probe / 'snapshot-1.json').exists() and logs().count('FEEDBACK_SNAPSHOT 1') == 2, 'reload removes observed-only blocks')
        reloaded = json.loads((probe / 'snapshot-1.json').read_text())
        assert [row['id'] for row in reloaded['shown']] == [row['id'] for row in native], reloaded
        mux('send-keys', '-t', 'test', 'F9')
        wait(lambda: 'FEEDBACK_OTHER_SESSION' in logs(), 'switch to a different session')
        mux('send-keys', '-t', 'test', 'F8')
        wait(lambda: logs().count('FEEDBACK_SNAPSHOT 2') == 2, 'other session snapshot')
        other = json.loads((probe / 'snapshot-2.json').read_text())
        assert other['shown'] == [] and other['outline']['messages'] == [], other
        mux('send-keys', '-t', 'test', 'F10')
        wait(lambda: 'FEEDBACK_ORIGINAL_SESSION' in logs() and 'FEEDBACK_COMPLETE' in screen(), 'return to unchanged engine history')
        mux('send-keys', '-t', 'test', 'F8')
        wait(lambda: logs().count('FEEDBACK_SNAPSHOT 3') == 2, 'original session snapshot')
        original = json.loads((probe / 'snapshot-3.json').read_text())
        assert [row['id'] for row in original['shown']] == [row['id'] for row in native], original
        assert len(requests) == 2, requests
        assert not any(tool['function']['name'] == 'phase_timing' for request in requests for tool in request.get('tools', [])), requests
        assert 'waiting for model ·' not in json.dumps(requests) and 'receiving response ·' not in json.dumps(requests), requests
        assert '[error]' not in logs(), logs()
        print('PASS streamed partial answer, thought-style heading/fold/activation, transcript placement, queue preservation, engine/context isolation, frozen clocks, narrow layout, session isolation, live reasoning/speed/tool, one idle-aware clock, and reload cleanup', flush=True)
    finally:
        (root / 'captures.txt').write_text('\n'.join(captures))
        (root / 'requests.json').write_text(json.dumps(requests, indent=2))
        subprocess.run(['tmux', '-L', mux_socket, 'kill-server'], capture_output=True)
        provider.shutdown()
        provider.server_close()


if __name__ == '__main__':
    main()
