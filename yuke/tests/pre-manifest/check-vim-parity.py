#!/usr/bin/env python3
"""Compare profile edits and caret positions with headless Vim. Use isolated stores and no clipboard."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

profile = Path(__file__).resolve().parents[1]
# Match the profile's fixed indentation and single-space line joins.
cases = [
    ("abc def", 0, "rx"), ("abc def", 1, "2rx"), ("abc", 1, "3rx"),
    ("abc def", 0, "r/"), ("abc def", 0, "r\r"), ("abc def", 0, "2r\r"),
    ("abc", 0, "o\x1b"), ("abc", 0, "O\x1b"),
    ("abc def", 0, "rxw."), ("abc", 0, "rxu"),
    ("one\n  two\nthree", 0, "J"), ("one\n  two\nthree", 1, "3J"),
    ("one\n  two\nthree", 0, "gJ"), ("one\n  two\nthree", 0, "3gJ"),
    ("one\ntwo\nthree", 0, "J."), ("one\ntwo", 4, "J"),
    ("one \n two", 0, "J"), ("one.\ntwo", 0, "J"), ("one\n )", 0, "J"),
    ("\n  two", 0, "j0k"), ("\n  two", 0, "h"), ("\n  two", 0, "l"),
    ("one\n\nthree", 0, "3J"), ("\n  two", 0, "J"),
    ("one\ntwo\nthree", 0, "VjJ"), ("one\n  two", 0, "VgJ"),
    ("abc def", 0, "RXY\x1b"), ("abc", 1, "RXYZ\x1b"),
    ("abc", 0, "RXY\x08\x1b"), ("abc", 0, "RX\x08\x08\x1b"),
    ("abc def", 0, "RXY\x1bw."), ("abc def", 0, "RXY\x1bu"),
    ("abc def", 0, "RXY\x1bu\x12"), ("a\nb", 0, "3RX\x1b"),
    ("abc def ghi", 0, "RXY\x1bw.w."), ("abc def", 0, "RXY\x08\x1bw."), ("abc def", 0, "2RX\x1b"),
    ("AbC dEf", 0, "~"), ("AbC dEf", 0, "3~"), ("AbC", 1, "5~"),
    ("AbC dEf", 0, "gUiw"), ("AbC dEf", 0, "guw"), ("AbC dEf", 0, "g~w"),
    ("AbC\ndEf\nGhI", 0, "2gUU"), ("AbC\ndEf", 0, "guj"),
    ("AbC dEf", 0, "gUiw w."), ("AbC", 0, "vlU"), ("AbC", 0, "vlu"),
    ("AbC", 0, "vl~"), ("AbC\ndEf", 0, "Vjg~"),
    ("one\ntwo\nthree", 0, ">>"), ("one\ntwo\nthree", 0, "2>>"),
    ("one\ntwo\nthree", 0, ">j"), ("  one\n    two", 0, "2<<"),
    ("one\ntwo\nthree", 0, "Vj>"), ("one\ntwo", 0, "Vj3>"),
    ("one\ntwo\nthree", 0, ">>j."), ("one\ntwo", 0, ">>u"),
    ("\tone", 0, ">>"), ("  \tone", 0, "<<"), ("  \n\none", 0, "3>>"),
    ("abc def", 3, "X"), ("abc def", 3, "2X"), ("abc def", 0, "Yp"),
    ("abc\ndef", 0, "2SXY\x1b"),
    ("abc def", 0, "yiwwviwp"), ("abc def", 0, "yiwwviwP"),
    ("abc\ndef", 0, "yyjvp"), ("abc\ndef", 0, "yyjVp"),
    ("abc\ndef", 0, "yiwjVp"), ("abc\ndef", 0, "yiwjVP"),
    ("abc def", 0, "vl\x1bgvy"), ("abc def", 0, '"ayiw w"ap'),
    ("abc def", 0, '"ayiw w"Ayiw $p'), ("abc\ndef", 0, '"ayy j"Ayy p'),
    ("abc def", 0, 'yiww"_diwP'), ("abc def", 0, 'yiwwdiw"0P'),
    ("abc\ndef\nghi", 0, 'dd dd"2p'), ("abc def", 0, 'dw"-P'),
    ("abc def", 0, "maw`a"),
    ("one\nother", 0, '"ayiw j"Ayy p'), ("one\nother", 0, '"ayy j"Ayiw p'), ("  abc\n  def", 3, "maG'a"),
    ("abc def", 4, "max`a"), ("abc def", 4, "ma0iX\x1b`a"),
    ("abc def", 4, "ma0iX\x1bu`a"), ("abc\ndef\nghi", 0, "maGd'a"),
    ("abc\ndef\nghi", 1, "maGd`a"),
    ("one ones one one", 0, "*"), ("one ones one one", 0, "2*"),
    ("one ones one one", 0, "*N"), ("one ones one one", 0, "*n"),
    ("one ones one one", 0, "#"), ("one ones one one", 0, "g*"),
    ("one ones one one", 0, "g#"), ("  one two one", 0, "*"),
    ("one two one", 0, "d*"), ("one two one", 0, "*0dn"),
    ("abc def", 0, '"ayiwAi\x12a\x1b'), ("abc\ndef", 0, 'yyAi\x12"\x1b'),
    ("abc def", 0, "f/"), ("abc def", 0, "vllrx"), ("abc\ndef", 0, "Vjrx"),
    ("abc def", 0, "vllr\r"), ("abc\ndef", 0, "Vjr\r"),

]


def vim_string(value):
    return json.dumps(value, ensure_ascii=False).replace("\\u001b", "\\x1b").replace("\\u0012", "\\x12").replace("\\b", "\\x08")


with tempfile.TemporaryDirectory(prefix="yuke-vim-parity-") as directory:
    tmp = Path(directory)
    expected = tmp / "expected.jsonl"
    commands = ["set nomore nojoinspaces shiftwidth=2 tabstop=2 expandtab", f"call writefile([], {vim_string(str(expected))})"]
    for text, at, strokes in cases:
        commands += ['execute "normal! \x1b"', "enew!", "call setline(1, " + json.dumps(text.split("\n"), ensure_ascii=False) + ")"]
        row = text[:at].count("\n") + 1
        column = len(text[:at].rsplit("\n", 1)[-1].encode()) + 1
        commands += ["let &undolevels = &undolevels", f"call cursor({row}, {column})", "execute 'normal! ' . " + vim_string(strokes)]
        commands += [f"call writefile([json_encode({{'text': join(getline(1, '$'), \"\\n\"), 'caret': line2byte(line('.')) - 1 + col('.') - 1}})], {vim_string(str(expected))}, 'a')"]
    commands += ["qa!"]
    script = tmp / "reference.vim"
    script.write_text("\n".join(commands) + "\n")
    subprocess.run(["vim", "-Nu", "NONE", "-i", "NONE", "-n", "-es", "-S", str(script)], check=True, timeout=30)
    results = [json.loads(line) for line in expected.read_text().splitlines()]
    # The profile restores snapshot carets for undo and redo, not Vim's change-start caret.
    snapshot_carets = {"rxu", "RXY\x1bu", "RXY\x1bu\x12", ">>u"}
    for case, result in zip(cases, results):
        result["checkCaret"] = case[2] not in snapshot_carets
    assert len(results) == len(cases)
    generated = tmp / "yuke"
    generated.mkdir()
    (generated / "index.js").write_text('''import { plugins } from "yuke";
import { ChatView } from "yuke:chat";
import { vimImproved } from ''' + json.dumps(str(profile / "plugins/vim-improved.js")) + ''';
plugins.use(vimImproved);
plugins.use({ name: "vim-parity", apply(ctx) {
 ctx.inject(["tui", "composer-vim"], c => {
  const view = c.tui.root.active;
  if (!(view instanceof ChatView)) throw Error("missing chat");
  const input = view.composer.input, mode = c["composer-vim"];
  view.composer.layout({x: 0, y: 0, w: 80, h: 20});
  const cases = ''' + json.dumps(cases, ensure_ascii=False) + ''';
  const expected = ''' + json.dumps(results, ensure_ascii=False) + ''';
  let failures = 0;
  for (let n = 0; n < cases.length; n++) {
   const [text, at, strokes] = cases[n];
   view.focusRegion("composer"); mode.setMode(view.composer, "insert");
   input.setText(text); input.caret = at; mode.setMode(view.composer, "normal");
   for (const char of strokes) {
    const code = char === "\\x1b" ? "esc" : char === "\\x08" ? "backspace" : char === "\\r" ? "enter" : "char";
    const mods = char === "\\x12" ? 4 : 0, value = mods ? "r" : code === "char" ? char : "";
    c.tui.root.onEvent({ type: "key", code, event: "press", char: value, text: mods ? "" : value, mods, shifted: "", baseLayout: "" });
   }
   if (input.text !== expected[n].text || (expected[n].checkCaret && input.caret !== expected[n].caret)) {
    failures++;
    c.print(JSON.stringify({n, strokes, initial: text, actual: {text: input.text, caret: input.caret}, expected: expected[n]}));
   }
  }
  if (failures) throw Error(failures + " Vim parity differences");
  c.print(cases.length + " Vim text comparisons and " + expected.filter(result => result.checkCaret).length + " caret comparisons passed");
 });
}});
''')
    env = os.environ.copy()
    env.update(XDG_CONFIG_HOME=directory, XDG_DATA_HOME=directory + "/data", XDG_STATE_HOME=directory + "/state", YUKE_APPNAME="yuke")
    subprocess.run(["yuke", "check"], env=env, check=True, timeout=60)
