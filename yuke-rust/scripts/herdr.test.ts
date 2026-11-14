import { assert, assertEquals, createHost, test } from "yuke:test";
import type { NavigationBridge } from "../.config/yuke-rust/navigation.ts";
import { apply } from "../.config/yuke-rust/plugins/herdr/index.ts";

test("Herdr navigation uses the private test server and preserves the session UUID", async () => {
  const shared: { bridge?: NavigationBridge | undefined } = {};
  await using _host = await createHost({
    plugins: [
      {
        name: "navigation",
        provides: ["personal-navigation"],
        apply: (ctx) => {
          ctx.provide("personal-navigation", {
            installBridge: (bridge) => {
              shared.bridge = bridge;
              return () => {
                shared.bridge = undefined;
              };
            },
            openSession: async () => {},
            openFile: async () => {},
          });
        },
      },
      { name: "herdr", apply },
    ],
  });
  const bridge = shared.bridge;
  assert(bridge !== undefined);
  assertEquals(await bridge.focusSession("019a3d2b-1234-7000-8000-000000000002"), true);
  assertEquals(await bridge.focusSession("019a3d2b-1234-7000-8000-000000000003"), false);
  await bridge.openFile("file:///tmp/a%20b.rs#L7C2", "/tmp");
});
