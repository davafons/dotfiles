/** @param {import("yuke").Context} ctx */
export default function (ctx) {
  const dash = ctx.get("yuke-dashboard");
  dash.setup({
    footer: "unleash your harness",
    rows: [
      { command: "auth:login", label: "Sign in", key: "l" },
      { command: "ui:sessions", label: "Resume a session", key: "r" },
      { command: "search:open", label: "Search chats and files", key: "s" },
      { command: "project-work:work", label: "Project tasks and checkpoints", key: "w" },
      { command: "model:pick", label: "Choose a model", key: "m" },
      { command: "ui:palette", label: "Commands", key: "c" },
      { command: "quit", label: "Quit Yuke", key: "q" },
    ],
  });
}
