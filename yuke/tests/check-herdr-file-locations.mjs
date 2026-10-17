#!/usr/bin/env node
import assert from "node:assert/strict";
import { fileLocation, fileReferenceAt, fileToolLocation } from "../.config/yuke/plugins/herdr/file-locations.js";

for (const [value, expected] of [
  ["src/app.ts:42:5", {path: "src/app.ts", line: 42, column: 5}],
  ["README.md#L12-L20", {path: "README.md", line: 12}],
  ['"folder with spaces/file.txt:2"', {path: "folder with spaces/file.txt", line: 2}],
  ["file:///tmp/a%20file%23name.txt#L3C2", {path: "/tmp/a file#name.txt", line: 3, column: 2}],
  ["file://localhost/tmp/file.txt", {path: "/tmp/file.txt"}],
  ["~/notes.md", {path: "~/notes.md"}],
  ["https://example.com/file.ts:20", null],
  ["file://another-host/tmp/file.txt", null],
  ["javascript:alert(1)", null],
  ["mailto:someone@example.com", null],
  ["src/file.ts:999999999999999999999", null],
  ["file:///tmp/%ZZ", null],
  ["file:///tmp/%00evil", null],
  ["src/file\n.txt", null],
]) assert.deepEqual(fileLocation(value), expected, value);

for (const [source, target, expected] of [
  ["See [the implementation](src/main.ts#L42).", "implementation", {path: "src/main.ts", line: 42}],
  ["See [a spaced file](<src/a file.txt:2:4>).", "spaced", {path: "src/a file.txt", line: 2, column: 4}],
  ["Read [this file](src/a%20file.txt#L5).", "this", {path: "src/a file.txt", line: 5}],
  ["Read `src/app.ts:8:2` next.", "app", {path: "src/app.ts", line: 8, column: 2}],
  ["Read `folder with spaces/file.txt:2`.", "spaces", {path: "folder with spaces/file.txt", line: 2}],
  ["Changed src/file.ts:9, then README.md.", "file", {path: "src/file.ts", line: 9}],
  ["Changed src/file.ts:9, then README.md.", "README", {path: "README.md"}],
  ["[the web](https://example.com/file.ts)", "web", null],
  ["![image](src/image.png)", "image", null],
  ["Nothing to open here.", "Nothing", null],
  ["[bad](bad%ZZ.txt)", "bad", null],
]) assert.deepEqual(fileReferenceAt(source, source.indexOf(target) + 1), expected, source);
assert.equal(fileReferenceAt("README.md", -1), null);
assert.equal(fileReferenceAt("README.md", 9), null);
assert.equal(fileReferenceAt("README.md.", 9), null);
const heading = {header: true, segments: [
  {text: "edit", src: 0, srcEnd: 4},
  {text: " sample file.txt", src: 4, srcEnd: 20},
  {text: " · <1s"},
]};
const edit = {type: "tool", name: "edit", arguments: '{"path":"sample file.txt"}'};
assert.deepEqual(fileToolLocation(edit, heading, 7), {path: "sample file.txt"});
for (const column of [-1, 0, 3, 4, 20, 21, 100]) assert.equal(fileToolLocation(edit, heading, column), null);
assert.equal(fileToolLocation(edit, {...heading, header: false}, 7), null);
assert.deepEqual(fileToolLocation({...edit, name: "read", arguments: '{"path":"/tmp/a#L90:2","start":12}'}, heading, 7),
  {path: "/tmp/a#L90:2", line: 12}, "tool paths are literal data, not file:line strings");
assert.deepEqual(fileToolLocation({...edit, name: "write"}, heading, 7), {path: "sample file.txt"});
assert.deepEqual(fileToolLocation(edit, {header: true, segments: [{text: "edit", src: 0}, {text: " sample…", src: 4, srcEnd: 20}]}, 7),
  {path: "sample file.txt"}, "a clipped display still uses the complete metadata path");
for (const part of [undefined, {...edit, name: "exec"}, {...edit, arguments: "{"}, {...edit, arguments: "null"},
  {...edit, arguments: '[{"path":"sample file.txt"}]'}, {...edit, arguments: '{"path":3}'}, {...edit, arguments: '{"path":""}'}]) {
  assert.equal(fileToolLocation(part, heading, 7), null);
}
console.log("PASS local references and file-tool metadata, filename hit bounds, literal paths, clipped labels and nonfile rejection");
