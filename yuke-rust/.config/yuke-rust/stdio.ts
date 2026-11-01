import { mkdir, remove } from "yuke:fs";
import { ConnectionError, connect, type UnixConnection } from "yuke:net";
import { Command } from "yuke:process";

/** Own one private subprocess connection. Stdin stays out of argv, environment, files, and diagnostics. */
export async function stdio<T>(
  argv: readonly string[],
  cwd: string,
  signal: AbortSignal,
  run: (connection: {
    write: (text: string) => Promise<void>;
    read: () => Promise<{ stream: "stdout" | "stderr"; text: string } | { code: number }>;
  }) => Promise<T>,
): Promise<T> {
  const directory = `/tmp/yuke-io-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  await mkdir(directory, { mode: 0o700 });
  const path = `${directory}/io.sock`;
  const stopped = new AbortController();
  const lifetime = AbortSignal.any([signal, stopped.signal]);
  let ended = false;
  const process = new Command("python3", {
    args: [`${import.meta.dirname}/helpers/stdio-bridge.py`, path],
    cwd,
    signal: lifetime,
  })
    .output()
    .finally(() => {
      ended = true;
    });
  // Observe early failures while the socket starts; await the same result during cleanup.
  void process.catch(() => {});
  let connection: UnixConnection | undefined;
  try {
    for (let attempt = 0; attempt < 100; attempt += 1) {
      lifetime.throwIfAborted();
      try {
        connection = await connect({ transport: "unix", path, signal: lifetime });
        break;
      } catch (error) {
        if (!(error instanceof ConnectionError) || (error.code !== "ENOENT" && error.code !== "ECONNREFUSED") || ended)
          throw error;
        await new Promise<void>((resolve) => setTimeout(resolve, 10));
      }
    }
    if (connection === undefined) throw new Error("The private subprocess did not start.");
    const socket = connection;
    await socket.write(new TextEncoder().encode(`${JSON.stringify({ argv, cwd })}\n`));
    const reader = socket.readable.getReader();
    const decoder = new TextDecoder();
    let buffered = "";
    try {
      return await run({
        write: (text) => socket.write(new TextEncoder().encode(`${JSON.stringify({ type: "stdin", text })}\n`)),
        read: async () => {
          for (;;) {
            const newline = buffered.indexOf("\n");
            if (newline < 0) {
              const chunk = await reader.read();
              if (chunk.done) throw new Error("The private subprocess closed before its exit record.");
              buffered += decoder.decode(chunk.value, { stream: true });
              if (buffered.length > 128 * 1024) throw new Error("The private subprocess record is too large.");
              continue;
            }
            const value: unknown = JSON.parse(buffered.slice(0, newline));
            buffered = buffered.slice(newline + 1);
            if (typeof value !== "object" || value === null || !("type" in value))
              throw new Error("Invalid private subprocess record.");
            if (value.type === "started") continue;
            if (value.type === "exit" && "code" in value && typeof value.code === "number") return { code: value.code };
            if (
              (value.type === "stdout" || value.type === "stderr") &&
              "text" in value &&
              typeof value.text === "string"
            ) {
              return { stream: value.type, text: value.text };
            }
            throw new Error("Invalid private subprocess output.");
          }
        },
      });
    } finally {
      reader.releaseLock();
    }
  } finally {
    connection?.close();
    stopped.abort();
    // Cleanup aborts the owned subprocess, including a pending output request.
    await process.catch(() => {});
    await remove(directory, { recursive: true, force: true });
  }
}
