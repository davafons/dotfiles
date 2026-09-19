# Camofox backend

Use Hermes's browser tool with the persistent Camofox service configured by
the runtime. Do not add a browser MCP, raw CDP connection, local executable, or
another browser backend.

Keep each conversation and activity in its own browser session or tab group.
Use separate sessions for genuinely parallel flows, and never reuse a session
owned by another agent. Camofox remains visible through the runtime's noVNC
surface so David can inspect, log in, or repair a page; pause while he has
control and refresh the page snapshot before continuing.

For ordinary navigation, use browser snapshots and element references. For
web-app debugging, collect console and network evidence in the affected task
tab and enable a session trace when available. Do not access cookies, profile
files, or the Camofox API directly. Stop before irreversible production
actions.
