---
name: playwright-cli
description: Drive a real browser — navigate, click, type, snapshot, read console and network. Use for any web automation, page inspection, or checking a local app in a browser.
---

# Browser automation with `playwright-cli`

Browser work goes through the **`playwright-cli` command**, not an MCP server. The CLI
writes snapshots, console logs and network dumps to `.playwright-cli/` in the working
directory and prints only a short result, so you read just the part you need instead of
pulling whole accessibility trees into context.

## Connect

The browser is the user's real, logged-in Brave profile, exposed over CDP on port 9222.
Make sure it is up, then attach once per session:

```bash
brave-agent                                        # idempotent; prints "ready: <url>"
playwright-cli attach --cdp=http://127.0.0.1:9222
```

`brave-agent` prompts before restarting an already-open Brave, because opening the port
costs the user their tabs. If it says "Nothing changed", respect that and stop.

## Core loop

```bash
playwright-cli snapshot            # element refs (e3, e15...) -> written to disk
playwright-cli find "Sign in"      # search the snapshot instead of reading it all
playwright-cli click e15
playwright-cli fill e5 "text" --submit
playwright-cli goto https://example.com
playwright-cli eval "() => document.title"
```

Read results back with ordinary shell tools — that is the point:

```bash
playwright-cli console             # note: logged objects collapse to "Object";
playwright-cli eval "..."          #   use eval when you need an object's fields
playwright-cli requests            # numbered; then: request <n>, response-body <n>
grep -h "MyTag" .playwright-cli/console-*.log
```

## Rules

- **Never hijack the tab the user is on.** `playwright-cli tab-new <url>` for your own work,
  and `tab-close` when done.
- `.playwright-cli/` is scratch output; it is globally gitignored. Don't commit it.
- `playwright-cli detach` when finished. It leaves the browser running.

## Full reference

`playwright-cli --help` lists every command; `--help <command>` details one. The complete
upstream skill ships inside the npm package — its path is printed at the top of `--help`.
