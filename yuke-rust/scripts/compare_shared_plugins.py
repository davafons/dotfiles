#!/usr/bin/env python3
"""Compare shared Vim and subagents with the personal profile using a model-free test host."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--upstream', type=Path, default=Path.home() / 'workspace/yuke-rust-plugins-upstream',
                    help='A tree of lostcoords/yuke-plugins at the pinned commit (39483ed), such as a git archive.')
parser.add_argument('--binary', type=Path, default=Path.home() / '.local/lib/yuke-rust/bin/yuke')
parser.add_argument('--output', type=Path, default=Path.home() / 'workspace/yuke/target/shared-plugin-comparison')
args = parser.parse_args()
upstream = args.upstream.resolve(strict=True)
binary = args.binary.resolve(strict=True)
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
profile = ROOT / '.config/yuke-rust'
plugins = profile / 'plugins'
report = {'upstream': str(upstream), 'binary': str(binary), 'plugins': {}, 'checks': []}
patches = []
for shared, personal in [('vim', 'vim'), ('subagents', 'agent-tools')]:
    left, right = upstream / 'plugins' / shared, plugins / personal
    files = {}
    for name in sorted({str(p.relative_to(base)) for base in (left, right) for p in (base / 'src').rglob('*.ts')}):
        a, b = left / name, right / name
        status = 'identical' if a.exists() and b.exists() and a.read_bytes() == b.read_bytes() else (
            'personal-only' if not a.exists() else 'upstream-only' if not b.exists() else 'changed')
        files[name] = {'status': status, **{
            label: hashlib.sha256(path.read_bytes()).hexdigest()
            for label, path in [('upstream_sha256', a), ('personal_sha256', b)] if path.exists()
        }}
        if status != 'identical':
            patches.extend(difflib.unified_diff(
                a.read_text().splitlines(keepends=True) if a.exists() else [],
                b.read_text().splitlines(keepends=True) if b.exists() else [],
                fromfile=f'upstream/{shared}/{name}', tofile=f'personal/{personal}/{name}'))
    report['plugins'][shared] = files
report['vim_consumers'] = sorted(
    str(p.relative_to(profile)) for p in plugins.rglob('*.ts')
    if p.parent != plugins / 'vim' / 'src' and 'get("composer-vim")' in p.read_text())
(output / 'source.diff').write_text(''.join(patches))

contract = '''import type { PluginContext } from "yuke:plugins";
import { assert, assertEquals, createFrame, createHost, reply, test } from "yuke:test";
import { TextEditor } from "yuke:tui";
import type { ComposerVim } from __SERVICE__;
import { apply as vimApply } from __VIM__;
import { apply as agentsApply, session as agentsSession } from __AGENTS__;

test("other plugins can observe, change and cancel composer Vim modes", () => {
  const editor = new TextEditor({ role: "composer" });
  using frame = createFrame({ width: 40, height: 10 }, () => editor);
  const surface = frame.surface("vim");
  let service: ComposerVim | undefined;
  vimApply({
    get: (name: string) => name === "tui" ? surface.tui : undefined,
    provide: (name: string, value: ComposerVim) => { if (name === "composer-vim") service = value; },
    signal: surface.signal,
  } as unknown as PluginContext);
  frame.draw();
  assert(service !== undefined, "Vim does not provide the service required by the personal plugins");
  const modes: string[] = [];
  const stop = service.onMode((_editor, mode) => { modes.push(mode); });
  service.setMode(editor, "normal");
  frame.key("d");
  assert(service.pending(editor));
  service.cancel(editor);
  assert(!service.pending(editor));
  service.setMode(editor, "insert");
  assertEquals(service.mode(editor), "insert");
  assertEquals(modes, ["normal", "insert"]);
  stop();
});

test("a named delegate receives its role prompt and an engine model receipt", async () => {
  await using host = await createHost({
    plugins: [{ name: "agents", apply: agentsApply, session: agentsSession }],
    replies: [reply.text("Reviewed the fixture.")],
  });
  const parent = await host.openSession();
  const result = await parent.call(__SPAWN__, {
    __ROLE__
    description: "Review fixture", message: "Review this fixture.", background: false,
  });
  assert(!result.isError, result.text);
  assert(host.requests[0]?.system.includes("Read ~/.agents/skills/dav-mode/SKILL.md in full"),
    "The child did not receive the configured role prompt");
  assert(result.text.includes("Engine model receipt:"), "The result lacks the model receipt");
});
'''
for variant, base, agent, spawn in [
    ('personal', plugins, 'agent-tools', 'spawn_agent'),
    ('upstream', upstream / 'plugins', 'subagents', 'spawn_subagent'),
]:
    text = contract
    for key, value in {
        '__SERVICE__': json.dumps(str(plugins / 'vim/src/service.ts')),
        '__VIM__': json.dumps(str(base / 'vim/src/index.ts')),
        '__AGENTS__': json.dumps(str(base / agent / 'src/index.ts')),
        '__SPAWN__': json.dumps(spawn),
        '__ROLE__': 'agent: "dav-agent",' if variant == 'personal' else '',
    }.items():
        text = text.replace(key, value)
    (output / f'{variant}-contract.test.ts').write_text(text)

transcript = (plugins / 'vim/tests/transcript.test.ts').read_text()
transcript = transcript.replace('"../src/index.ts"', json.dumps(str(upstream / 'plugins/vim/src/index.ts')))
(output / 'upstream-transcript.test.ts').write_text(transcript)

shared_tests = (upstream / 'plugins/subagents/tests/subagents.test.ts').read_text()
scaffold = shared_tests.split('\ntest(', 1)[0]
parent_view_test = shared_tests.split('test("parallel runs share one view', 1)[1].split('\ntest(', 1)[0]
parent_view_test = 'test("parallel runs share one view' + parent_view_test
parent_view_test = (scaffold + '\n' + parent_view_test).replace(
    '"../src/index.ts"', json.dumps(str(plugins / 'agent-tools/src/index.ts'))).replace(
    '"../src/run-log.ts"', json.dumps(str(plugins / 'agent-tools/src/run-log.ts'))).replace(
    'const SPAWN = {', 'const SPAWN = { agent: "dav-agent",').replace('spawn_subagent', 'spawn_agent')
parent_view_test = parent_view_test.replace('assertEquals(viewsOfParent(), 1);', 'const firstViews = viewsOfParent();').replace(
    'assertEquals(viewsOfParent(), 2);', 'assertEquals([firstViews, viewsOfParent()], [1, 2]);')
(output / 'personal-parent-view.test.ts').write_text(parent_view_test)

checks = [
    ('upstream-vim', upstream / 'plugins/vim/tests', True),
    ('personal-vim', plugins / 'vim/tests', True),
    ('upstream-subagents', upstream / 'plugins/subagents/tests', True),
    ('personal-contract', output / 'personal-contract.test.ts', True),
    ('upstream-contract', output / 'upstream-contract.test.ts', False),
    ('upstream-transcript', output / 'upstream-transcript.test.ts', False),
    ('personal-parent-view', output / 'personal-parent-view.test.ts', True),
]
# Each expected failure names missing upstream behavior: the composer-vim service, the personal role prompts,
# and transcript navigation.
expected_failures = {
    'upstream-contract': ('0 passed, 2 failed', ['Vim does not provide the service', 'did not receive the configured role prompt']),
    'upstream-transcript': ('0 passed, 6 failed', ['at reader']),
}
failed = False
for name, path, expected_success in checks:
    log = output / f'{name}.log'
    with log.open('w') as stream:
        result = subprocess.run([str(binary), 'test', str(path)], stdout=stream, stderr=subprocess.STDOUT,
                                env=dict(os.environ, MONID_API_KEY='migration-fixture-key'))
    logged = log.read_text()
    summary = logged.strip().splitlines()[-1:]
    matched = (result.returncode == 0) == expected_success
    if not expected_success:
        expected_summary, fragments = expected_failures[name]
        matched &= summary == [expected_summary] and all(fragment in logged for fragment in fragments)
    check = {'name': name, 'exit_code': result.returncode, 'expected_success': expected_success,
             'matched': matched, 'summary': summary, 'log': str(log)}
    report['checks'].append(check)
    print(json.dumps(check), flush=True)
    failed |= not matched
(output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
raise SystemExit(1 if failed else 0)
