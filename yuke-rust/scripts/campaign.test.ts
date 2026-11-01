import { env } from "yuke:process";
import { assert, createHost, equal, rejects, reply, test } from "yuke:test";
import { apply, session } from "../.config/yuke-rust/plugins/agent-tools/src/index.ts";

test("campaign grants filter offered tools and reject tools outside the grant", async () => {
  const workspace = env.get("CAMPAIGN_FIXTURE_WORKSPACE");
  assert(workspace !== undefined);
  if (env.get("CAMPAIGN_EXPECT_INVALID") === "1") {
    await using host = await createHost({ plugins: [{ name: "agent-tools", apply, session }] });
    const root = await host.openSession({ cwd: workspace });
    await rejects(root.run("round.before", { context: [] }));
    equal(host.requests.length, 0);
    return;
  }
  await using host = await createHost({
    plugins: [
      { name: "agent-tools", apply, session },
      {
        name: "fixture-tool",
        session: (s) => {
          s.tools.define({
            name: "blocked_fixture",
            description: "Not in the campaign grant",
            concurrency: "parallel",
            parameters: { type: "object", properties: {} },
            execute: () => {
              throw new Error("A blocked tool ran.");
            },
          });
        },
      },
    ],
    replies: [reply.text("Captured the allowed catalog.")],
  });
  const root = await host.openSession({ cwd: workspace });
  await root.send("Check the bounded campaign catalog.");
  const names = host.requests[0]?.tools;
  assert(names !== undefined && names.length > 0);
  assert(names.every((name) => ["read", "write", "edit", "spawn_agent", "send_agent_input", "stop"].includes(name)));
  const blocked = await root.run("tool.before", {
    call: { callId: "fixture", name: "blocked_fixture", arguments: {} },
  });
  equal(blocked, { block: "Tool is not allowed in a bounded campaign." });
  equal(host.requests.length, 1);
});
