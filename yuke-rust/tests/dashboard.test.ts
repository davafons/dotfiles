import { assert, createFrame, equal, test } from "yuke:test";
import { Dashboard } from "../.config/yuke-rust/plugins/dashboard/view.ts";

const actions = [
  { label: "Sign in", key: "l", command: "login" },
  { label: "Resume a session", key: "r", command: "sessions" },
  { label: "Search chats and files", key: "s", command: "search" },
  { label: "Project tasks and GitHub", key: "w", command: "work" },
  { label: "Choose a model", key: "m", command: "model" },
  { label: "Commands", key: "c", command: "commands" },
  { label: "Quit Yuke", key: "q", command: "quit" },
];

test("the dashboard centers the original logo and context with clickable shortcuts on the right", () => {
  const invoked: string[] = [];
  const view = new Dashboard(actions, "~/workspace/project", (name) => {
    invoked.push(name);
  });
  view.model("gpt-6.1-sol medium");
  using frame = createFrame({ width: 80, height: 30 }, () => view);
  const rows = frame.frame.cells.map((row) => row.map((cell) => cell.text).join(""));
  equal(rows.filter((row) => row.includes("██") || row.includes("╚═╝")).length, 6);
  const workspace = rows.find((row) => row.includes("~/workspace/project"));
  assert(workspace !== undefined);
  equal(workspace.indexOf("~/workspace/project"), 30);
  assert(rows.some((row) => row.includes("gpt-6.1-sol medium")));
  const menu = rows.findIndex((row) => row.includes("Sign in"));
  equal([rows[menu]?.indexOf("Sign in"), rows[menu]?.lastIndexOf("l")], [13, 66]);
  frame.mouse({
    type: "mouse",
    action: "press",
    button: "left",
    column: 30,
    row: menu + 3,
    modifiers: { shift: false, alt: false, ctrl: false, super: false, hyper: false, meta: false },
  });
  equal(invoked, ["work"]);
  frame.mouse({
    type: "mouse",
    action: "press",
    button: "left",
    column: 70,
    row: menu + 3,
    modifiers: { shift: false, alt: false, ctrl: false, super: false, hyper: false, meta: false },
  });
  equal(invoked, ["work"]);
});

test("the dashboard uses its compact layout after resize and refreshes its model context", () => {
  const view = new Dashboard(actions, "~/workspace/project", () => {});
  using frame = createFrame({ width: 80, height: 30 }, () => view);
  view.model("new model high");
  frame.resize({ width: 26, height: 12 });
  const rows = frame.frame.cells.map((row) => row.map((cell) => cell.text).join(""));
  assert(rows.some((row) => row.trim() === "YUKE"));
  assert(rows.some((row) => row.includes("Project tasks") && row.includes("…") && row.trimEnd().endsWith("w")));
  assert(!rows.some((row) => row.includes("██")));
  frame.resize({ width: 80, height: 30 });
  assert(
    frame.frame.cells.some((row) =>
      row
        .map((cell) => cell.text)
        .join("")
        .includes("new model high"),
    ),
  );
});
