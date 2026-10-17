#!/usr/bin/env python3
"""Check grouped feature switches and real model choices in private Yuke terminals."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import time
import uuid

PROBE = r'''
import { client, env, fs } from "yuke";
import { Session, currentPane, showSession } from "yuke:session";
import { quit } from "yuke:ui";
export default function(ctx) {
  const tui = ctx.get("tui");
  if (!tui) return;
  let delayRead = null;
  ctx.advise(client, "sessionGet", "around", async (next, id) => {
    const entry = await next(id);
    if (id === delayRead && entry.session.reasoning === "high") await new Promise(done => setTimeout(done, 200));
    return entry;
  });
  const before = { model: tui.command.map["model:pick"].run, context: tui.command.map["context:show"].run };
  const segments = [];
  ctx.advise(Object.getPrototypeOf(tui.status), "add", "before", function(segment) { segments.push(segment); });
  const statusText = () => segments.filter(row => row.side === "right").map(row => row.render()).join(" · ");
  ctx.once("ui.started", async () => { try {
    const expected = JSON.parse(env.get("GROUP_EXPECTED"));
    function check(actual, value, label) { if (actual !== value) throw Error(label + ": " + actual + " != " + value); }
    const commands = new Set(tui.command.list().map(row => row.name));
    for (const [name, enabled] of Object.entries(expected.commands)) check(commands.has(name), enabled, name);
    if (expected.modelOverride !== undefined) check(tui.command.map["model:pick"].run !== before.model, expected.modelOverride, "model override");
    if (expected.contextOverride !== undefined) check(tui.command.map["context:show"].run !== before.context, expected.contextOverride, "context override");
    check(statusText().includes("tok/s"), !!expected.speed, "speed status");
    if (expected.models) {
      const catalog = await client.catalogList(null);
      const model = catalog.models.find(row => row.selector === "group-test/model");
      if (!model) throw Error("missing fixture model");
      const pane = currentPane();
      if (expected.startup) {
        for (let i = 0; i < 100 && !statusText().includes("medium"); i++) await new Promise(done => setTimeout(done, 10));
        check(statusText().includes("medium"), true, "startup effort shown on draft");
        const draft = new Session();
        const id = await draft.startChat(null, pane.composer);
        check((await client.sessionGet(id)).session.reasoning, "medium", "new chat inherits startup effort");
        draft.release();
        const saved = await client.sessionCreate({ workspace_path: (await fs.stat(".")).path, model: model.selector, reasoning: "high" });
        showSession(pane, saved.session.id);
        const { modelState } = await import("../plugins/models/state.js");
        modelState(ctx, tui).setDefault(model, "medium");
        check((await client.sessionGet(saved.session.id)).session.reasoning, "high", "startup default preserves saved-session effort");
        const next = new Session();
        const nextId = await next.startChat(null, pane.composer);
        check((await client.sessionGet(nextId)).session.reasoning, "medium", "saved pane still sets only new-chat defaults");
        next.release();
        showSession(pane, new Session());
      }
      pane.session.setModel(model, "high");
      await new Promise(done => setTimeout(done, 60));
      check(statusText().includes("high"), expected.effortStatus, "accepted draft effort");
      if (expected.effortCommand) {
        tui.command.perform("models:effort", "low");
        await new Promise(done => setTimeout(done, 100));
        check(statusText().includes("low"), expected.effortStatus, "effort command updates shared state");
      }
      if (expected.modelKey) check(tui.keymap.hints()["model:pick"], expected.modelKey, "custom model key");
      if (expected.alias) {
        const saved = await client.sessionCreate({ workspace_path: (await fs.stat(".")).path, model: model.selector, reasoning: "low" });
        showSession(pane, saved.session.id);
        for (let i = 0; i < 100 && !tui.command.available("models:preset-fixture"); i++) await new Promise(done => setTimeout(done, 10));
        check(tui.command.perform("models:preset-fixture"), true, "alias works without model picker");
        for (let i = 0; i < 100 && (await client.sessionGet(saved.session.id)).session.reasoning !== "high"; i++) await new Promise(done => setTimeout(done, 10));
        check((await client.sessionGet(saved.session.id)).session.reasoning, "high", "alias applies persisted effort");
        check(tui.keymap.hints()["models:preset-fixture"], "f8", "alias shortcut is configurable");
      }
      if (expected.effortStatus) {
        const saved = await client.sessionCreate({ workspace_path: (await fs.stat(".")).path, model: model.selector, reasoning: "high" });
        showSession(pane, saved.session.id);
        for (let i = 0; i < 100 && !statusText().includes("high"); i++) await new Promise(done => setTimeout(done, 10));
        check(statusText().includes("high"), true, "persisted reasoning refreshes on open");
        pane.session.setModel(model, "low");
        for (let i = 0; i < 100 && (await client.sessionGet(saved.session.id)).session.reasoning !== "low"; i++) await new Promise(done => setTimeout(done, 10));
        check((await client.sessionGet(saved.session.id)).session.reasoning, "low", "accepted saved-session reasoning");
        check(statusText().includes("low"), true, "status agrees with saved reasoning");
        const delayed = await client.sessionCreate({ workspace_path: (await fs.stat(".")).path, model: model.selector, reasoning: "high" });
        delayRead = delayed.session.id;
        showSession(pane, delayed.session.id);
        await new Promise(done => setTimeout(done, 20));
        pane.session.setModel(model, "low");
        await new Promise(done => setTimeout(done, 250));
        check(statusText().includes("low"), true, "older metadata cannot overwrite a newly accepted effort");
        delayRead = null;
      }
    }
    if (expected.insights) {
      const pane = currentPane();
      pane.composer.input.setText("unsent inspection draft");
      const selected = [
        ...(expected.commands["insights:status"] ? ["insights:status"] : []),
        ...(expected.contextOverride ? ["context:show"] : []),
        ...(expected.commands["insights:usage"] ? ["insights:usage"] : []),
      ];
      async function wait(condition, label) {
        for (let i = 0; i < 200; i++) { if (condition()) return; await new Promise(done => setTimeout(done, 10)); }
        throw Error(label);
      }
      for (const command of selected) for (let pass = 0; pass < 2; pass++) {
        const count = tui.root.overlays.length;
        check(tui.command.perform(command), true, command + " available");
        await wait(() => tui.root.overlays.length === count + 1, command + " did not open");
        const window = tui.root.overlays.at(-1);
        await wait(() => !window.content.loading, command + " did not finish reading");
        if (window.content.error) throw Error(command + ": " + window.content.error);
        check(pane.composer.text, "unsent inspection draft", command + " preserves draft");
        tui.root.popOverlay(window);
        check(tui.root.overlays.length, count, command + " closes");
      }
    }
    ctx.print("GROUP_PASS");
  } catch(error) { ctx.print("GROUP_FAIL", String(error)); } finally { quit(); } });
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=Path(shutil.which('yuke') or 'yuke'))
    parser.add_argument('--profile', type=Path, default=Path(__file__).resolve().parents[1] / '.config/yuke')
    parser.add_argument('--group', choices=['models', 'controls', 'run-feedback', 'insights', 'step-trace', 'all'], default='all')
    parser.add_argument('--case', help='run one named case within the selected group')
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    source = args.profile.resolve(strict=True)
    root = Path(tempfile.mkdtemp(prefix='yuke-groups-', dir='/tmp')).resolve()
    root.chmod(0o700)
    print('Artifacts:', root, flush=True)
    cases = {
      'models': [
        ('startup-default', {'startupModel': 'group-test/model', 'startupEffort': 'medium'}, {'commands': {'models:effort': True}, 'modelOverride': True, 'models': True, 'effortStatus': True, 'effortCommand': True, 'startup': True}),
        ('startup-user-choice', {'startupModel': 'group-test/model', 'startupEffort': 'medium'}, {'commands': {'models:effort': True}, 'modelOverride': True, 'models': True, 'effortStatus': True, 'effortCommand': True}),
        ('default', {}, {'commands': {'models:effort': True}, 'modelOverride': True, 'models': True, 'effortStatus': True, 'effortCommand': True}),
        ('disabled', {'picker': False, 'effortPicker': False, 'aliases': False, 'effortStatus': False}, {'commands': {'models:effort': False}, 'modelOverride': False}),
        ('effort-only', {'picker': False, 'aliases': False}, {'commands': {'models:effort': True}, 'modelOverride': False, 'models': True, 'effortStatus': True, 'effortCommand': True}),
        ('aliases-only', {'picker': False, 'effortPicker': False, 'effortStatus': False}, {'commands': {'models:effort': False}, 'modelOverride': False, 'models': True, 'effortStatus': False, 'alias': True}),
        ('picker-only', {'effortPicker': False, 'aliases': False, 'effortStatus': False, 'modelKey': 'f6'}, {'commands': {'models:effort': False}, 'modelOverride': True, 'models': True, 'effortStatus': False, 'modelKey': 'f6'}),
      ],
      'controls': [
        ('without-vim', {}, {'commands': {'controls:clear': True, 'controls:exit': True, 'controls:close': True, 'controls:panel': True}, 'vim': False}),
        ('default', {}, {'commands': {'controls:clear': True, 'controls:exit': True, 'controls:close': True, 'controls:panel': True}}),
        ('disabled', {'clearAlias': False, 'exitAliases': False, 'interrupt': False, 'navigation': False, 'panelCommand': False}, {'commands': {'controls:clear': False, 'controls:exit': False, 'controls:close': False, 'controls:panel': False}}),
        ('panel-only', {'clearAlias': False, 'exitAliases': False, 'interrupt': False, 'navigation': False}, {'commands': {'controls:clear': False, 'controls:exit': False, 'controls:panel': True}}),
      ],
      'run-feedback': [
        ('default', {}, {'commands': {}, 'speed': True}),
        ('disabled', {'tokenSpeed': False, 'phaseTimers': False, 'stepTimers': False}, {'commands': {}, 'speed': False}),
        ('speed-only', {'phaseTimers': False, 'stepTimers': False, 'speedRefreshMs': 500}, {'commands': {}, 'speed': True}),
      ],
      'step-trace': [
        ('default', {}, {'commands': {}, 'trace': False}),
        ('enabled', {'enabled': True}, {'commands': {}, 'trace': True}),
      ],
      'insights': [
        ('default', {}, {'commands': {'insights:status': True, 'insights:usage': True}, 'contextOverride': True, 'insights': True}),
        ('disabled', {'status': False, 'context': False, 'usage': False}, {'commands': {'insights:status': False, 'insights:usage': False}, 'contextOverride': False}),
        ('status-only', {'context': False, 'usage': False}, {'commands': {'insights:status': True, 'insights:usage': False}, 'contextOverride': False, 'insights': True}),
      ],
    }
    selected = list(cases) if args.group == 'all' else [args.group]
    for group in selected:
      selected_cases = [case for case in cases[group] if not args.case or case[0] == args.case]
      if not selected_cases:
        parser.error('unknown case for ' + group + ': ' + str(args.case))
      for name, settings, expected in selected_cases:
        case = root / (group + '-' + name)
        profile = case / 'config/yuke'
        shutil.copytree(source, profile, ignore=shutil.ignore_patterns('providers.json*', '*.key', '.env', 'yuke.d.ts', 'yuke-modules.d.ts', 'yuke.jsconfig.json', '__pycache__'))
        for folder in ['home', 'work', 'state', 'data', 'cache']:
            (case / folder).mkdir()
        probe = profile / 'probe'
        probe.mkdir()
        (probe / 'index.js').write_text(PROBE)
        (probe / 'plugin.json').write_text(json.dumps({'name': 'group-probe', 'extensions': {'sh.yuke': {'entry': './index.js', 'uses': ['tui']}}}))
        (profile / 'config.json').write_text(json.dumps({'plugins': (['./plugins/vim-mode'] if expected.get('vim', True) else []) + ['./probe', './plugins/' + group]}))
        (profile / 'plugins' / group / 'settings.json').write_text(json.dumps(settings))
        (profile / 'model-aliases.json').write_text(json.dumps({'version': 1, 'revision': 0, 'presets': [{'alias': 'fixture', 'model': 'group-test/model', 'effort': 'high', 'key': 'f8'}]}))
        (profile / 'providers.json').write_text(json.dumps({'providers': [{'id': 'group-test', 'base_url': 'http://127.0.0.1:1/v1', 'api_key': 'fixture-only', 'endpoints': [{'protocol': 'openai_chat', 'credential_header': 'authorization_bearer'}], 'models': [{'id': 'model', 'upstream_id': 'model', 'reasoning_levels': ['low', 'medium', 'high'], 'flags': {'thinking_format': 'openai'}, 'limits': {'context_window': 100000, 'max_output_tokens': 4096}}]}]}))
        (profile / 'providers.json').chmod(0o600)
        env = {'HOME': str(case / 'home'), 'PATH': os.environ['PATH'], 'TERM': 'xterm-256color', 'YUKE_APPNAME': 'yuke', 'GROUP_EXPECTED': json.dumps(expected)}
        for folder in ['config', 'state', 'data', 'cache']:
            env['XDG_' + folder.upper() + '_HOME'] = str(case / folder)
        mux_socket = 'group-' + uuid.uuid4().hex[:10]
        command = shlex.join(['env', '-i', *(f'{key}={value}' for key, value in env.items()), str(binary)])
        try:
            subprocess.run(['tmux', '-L', mux_socket, 'new-session', '-d', '-x', '120', '-y', '35', '-s', 'test', '-c', str(case / 'work'), command], check=True, capture_output=True)
            log = case / 'state/yuke/yuke.log'
            end = time.monotonic() + 15
            while time.monotonic() < end:
                text = log.read_text() if log.exists() else ''
                if 'GROUP_PASS' in text or 'GROUP_FAIL' in text:
                    break
                time.sleep(0.05)
            else:
                raise AssertionError(group + '/' + name + ' did not finish\n' + text)
            assert 'GROUP_PASS' in text and 'GROUP_FAIL' not in text and '[error]' not in text, group + '/' + name + '\n' + text
            if 'trace' in expected:
                assert ('STEP_TRACE ' in text) == expected['trace'], 'diagnostic opt-in was ignored\n' + text
            print('PASS', group, name, flush=True)
        finally:
            subprocess.run(['tmux', '-L', mux_socket, 'kill-server'], capture_output=True)
      switch = next(key for _, settings, _ in cases[group] for key, value in settings.items() if isinstance(value, bool))
      for invalid in [{'unknownFeature': True}, {switch: 'false'}]:
        (profile / 'plugins' / group / 'settings.json').write_text(json.dumps(invalid))
        result = subprocess.run([str(binary), 'check'], env=env, cwd=case / 'work', capture_output=True, text=True, timeout=15)
        assert result.returncode != 0 and ('Unknown setting' in result.stderr or 'must be boolean' in result.stderr), group + ' accepted invalid settings\n' + result.stdout + result.stderr
      print('PASS', group, 'rejects invalid settings', flush=True)


if __name__ == '__main__':
    main()
