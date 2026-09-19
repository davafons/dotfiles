//! Keep /reload resident while replacing every other profile plugin from fresh source.
import { client, env, exec, plugins } from "yuke";
import { currentSession } from "yuke:session";
import { profile as startupProfile } from "../profile.js";
/** @import { Plugin, PluginHandle } from "yuke" */

/** @param {string} value */
function shellQuote(value) {
  return "'" + value.replaceAll("'", "'\\''") + "'";
}

function paths() {
  const home = env.get("HOME") || ".";
  const app = env.get("YUKE_APPNAME") || "yuke";
  const config = env.get("XDG_CONFIG_HOME") || home + "/.config";
  const cache = env.get("XDG_CACHE_HOME") || home + "/.cache";
  return { source: config + "/" + app, cache: cache + "/" + app + "/profile-reload" };
}

/** The stable profile loader and complete `/reload` replacement. */
export const profileReloader = /** @type {Plugin} */ ({
  name: "profile-reloader",
  apply(ctx) {
    /** @type {Plugin} */
    let currentProfile = startupProfile;
    /** @type {PluginHandle} */
    let active = plugins.use(currentProfile);
    let generation = 0;
    let reloading = false;
    ctx.own(() => active.dispose());

    const reload = async () => {
      if (reloading) {
        ctx.interaction.notify("Profile reload already in progress.");
        return;
      }
      reloading = true;
      const sessionId = currentSession()?.sessionId;
      try {
        const location = paths();
        const destination = location.cache + "/" + Date.now() + "-" + (++generation);
        const command = [
          "/bin/rm -rf " + shellQuote(location.cache),
          "/bin/mkdir -p " + shellQuote(destination),
          "/bin/cp -RL " + ["profile.js", "plugins", "tools"].map((name) => shellQuote(location.source + "/" + name)).join(" ") + " " + shellQuote(destination),
        ].join(" && ");
        const copied = await exec(command, { signal: ctx.signal });
        if (copied.code !== 0) throw new Error((copied.stderr || copied.stdout || "could not copy profile").trim());

        const loaded = await import(destination + "/profile.js");
        /** @type {Plugin} */
        const nextProfile = loaded.profile;
        if (!nextProfile || nextProfile.name !== "user-profile" || typeof nextProfile.apply !== "function") {
          throw new TypeError("profile.js must export the user-profile plugin as `profile`");
        }
        if (!ctx.alive) return;

        const previousProfile = currentProfile;
        await active.dispose();
        try {
          active = plugins.use(nextProfile);
          currentProfile = nextProfile;
        } catch (error) {
          active = plugins.use(previousProfile);
          throw error;
        }

        if (!sessionId) {
          ctx.interaction.notify("Profile reloaded; no open chat context to reload.");
          return;
        }
        try {
          const result = await client.sessionReloadContext(sessionId);
          ctx.interaction.notify("Profile and context reloaded: " + result.instruction_sources.length + " AGENTS.md, " + result.skills.length + " skills.");
        } catch (error) {
          ctx.interaction.notify("Profile reloaded, but context reload failed: " + String(error), "warn");
        }
      } catch (error) {
        if (ctx.alive) ctx.interaction.notify("Profile reload failed: " + String(error), "error");
      } finally {
        reloading = false;
      }
    };

    ctx.inject(["tui"], (c) => {
      // The exact built-in name shadows its /reload entry while preserving its purpose.
      c.tui.command.add("context:reload", {
        desc: "reload profile plugins, AGENTS.md, and skills",
        slash: true,
        run: () => { void reload(); },
      });
    });
  },
});
