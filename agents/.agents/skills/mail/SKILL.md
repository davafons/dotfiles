---
name: mail
description: "Manage David's email, contacts, and drafts through HEY. Use for mail communication; not for calendar, tasks, todos, or journal entries."
---

# Mail

Before using the HEY CLI, read its internal adapter manual. Use
`$PERSONAL_SKILLS_ADAPTER_DIR/hey/SKILL.md` when that variable is set;
otherwise use `~/.agents/skills/hey/SKILL.md`. The provider skill is
intentionally hidden from normal skill discovery; do not copy its manual into
this facade.

- Read, search, organize, and draft mail when requested.
- Prefer drafts for new messages and replies unless David explicitly asks to send.
- Treat sending, forwarding, deleting, moving, labels, and contact changes as state-changing actions and confirm the exact target and content when it is not already explicit.

Calendar events and time blocks belong to `calendar`. Task capture and completion belong to `tasks`. Do not create HEY todos as a separate task system.
