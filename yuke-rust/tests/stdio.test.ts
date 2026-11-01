import { assert, equal, test } from "yuke:test";
import { stdio } from "../.config/yuke-rust/stdio.ts";

test("private subprocess stdin and split Unicode output cross the socket without entering process output", async () => {
  const controller = new AbortController();
  const chunks: string[] = [];
  await stdio(
    [
      "python3",
      "-c",
      "import sys; value=sys.stdin.readline().strip(); sys.stdout.buffer.write(('你好 '+value).encode()); sys.stdout.flush(); sys.stderr.write('complete')",
    ],
    "/tmp",
    controller.signal,
    async (connection) => {
      await connection.write("fixture input\n");
      for (;;) {
        const event = await connection.read();
        if ("code" in event) {
          equal(event.code, 0);
          break;
        }
        chunks.push(event.text);
      }
    },
  );
  const text = chunks.join("");
  assert(text.includes("你好 fixture input") && text.includes("complete"), text);
});

test("a private subprocess flushes an incomplete final UTF-8 character", async () => {
  let text = "";
  await stdio(
    ["python3", "-c", "import sys; sys.stdout.buffer.write(b'hello\\xe4')"],
    "/tmp",
    new AbortController().signal,
    async (connection) => {
      for (;;) {
        const event = await connection.read();
        if ("code" in event) {
          equal(event.code, 0);
          break;
        }
        text += event.text;
      }
    },
  );
  equal(text, "hello�");
});
