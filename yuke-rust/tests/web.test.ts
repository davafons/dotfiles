import { env } from "yuke:process";
import { assert, createHost, equal, test } from "yuke:test";
import { session as webSession } from "../.config/yuke-rust/plugins/web/index.ts";

test("web search and fetch preserve their request shapes and bound returned text", async () => {
  assert(
    env.get("MONID_API_KEY") === "migration-fixture-key",
    "Run through scripts/verify.py so this check uses its fixture key.",
  );
  const original = globalThis.fetch;
  const requests: unknown[] = [];
  globalThis.fetch = async (_url, options) => {
    assert(
      new Headers(options?.headers).get("Authorization") === "Bearer migration-fixture-key",
      "The fixture key did not reach the request.",
    );
    const body = JSON.parse(String(options?.body)) as { endpoint: string };
    requests.push(body);
    return new Response(
      JSON.stringify({
        status: "COMPLETED",
        output: {
          results:
            body.endpoint === "/free/search"
              ? Array.from({ length: 8 }, (_, index) => ({
                  title: `Result ${index}`,
                  url: `https://example.com/${index}`,
                  snippet: "snippet ".repeat(100),
                }))
              : [{ title: "Fixture page", final_url: "https://example.com/final", text: "page text ".repeat(1000) }],
        },
      }),
    );
  };
  try {
    await using host = await createHost({ plugins: [{ name: "web", session: webSession }] });
    const session = await host.openSession();
    const search = await session.call("web_search", { query: "migration fixture" });
    assert(!search.isError, search.text);
    equal((search.text.match(/^\d\./gm) ?? []).length, 5);
    assert(!search.text.includes("Result 5"));
    const page = await session.call("web_fetch", { url: "https://example.com/source" });
    assert(!page.isError, page.text);
    assert(
      page.text.includes("https://example.com/final") && page.text.endsWith("[truncated]") && page.text.length < 4100,
    );
    equal(requests, [
      { provider: "tinyfish", endpoint: "/free/search", input: { queryParams: { query: "migration fixture" } } },
      {
        provider: "tinyfish",
        endpoint: "/free/fetch",
        input: { body: { urls: ["https://example.com/source"], format: "markdown" } },
      },
    ]);
    equal(host.requests.length, 0);
  } finally {
    globalThis.fetch = original;
  }
});
