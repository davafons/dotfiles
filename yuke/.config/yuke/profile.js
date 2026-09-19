//! Reloadable user profile. The stable loader owns this parent plugin.
import { agents, mcp } from "yuke:plugins";
import { clearAlias } from "./plugins/clear-alias.js";
import { ctrlC } from "./plugins/ctrl-c.js";
import { effortStatus } from "./plugins/effort-status.js";
import { modelsNewestFirst } from "./plugins/models-newest-first.js";
import { promptHistory } from "./plugins/prompt-history.js";
import { herdr } from "./plugins/herdr.js";
import { insertStatusLeft } from "./plugins/insert-status-left.js";
import { sessionsReworked } from "./plugins/sessions-reworked.js";
import { solarizedTheme } from "./plugins/solarized-theme.js";
import { web } from "./tools/web.js";
/** @import { Plugin } from "yuke" */

/** Every profile-owned plugin under one disposable parent. */
export const profile = /** @type {Plugin} */ ({
  name: "user-profile",
  apply(ctx) {
    ctx.use(solarizedTheme);
    ctx.use(insertStatusLeft);
    ctx.use(effortStatus);
    ctx.use(clearAlias);
    ctx.use(ctrlC);
    ctx.use(modelsNewestFirst);
    ctx.use(promptHistory);
    ctx.use(sessionsReworked);
    ctx.use(herdr());
    ctx.use(mcp());
    ctx.use(web);

    // One general child with every tool, on Codex Luna whatever the parent runs.
    ctx.use(agents({
      catalog: {
        general: { description: "A capable general agent. Give it one self-contained task.", model: "openai-codex/gpt-6-luna" },
      },
    }));
  },
});
