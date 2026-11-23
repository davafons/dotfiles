---
name: mail
description: "Manage David's email and drafts through Zoho Mail with the himalaya CLI. Use for mail communication; not for calendar, tasks, todos, or journal entries."
---

# Mail

David's mail lives in Zoho: mailbox `dav@lostcoords.com`, sending as
`David Afonso <dav@davafons.com>` (an alias). Every `*@davafons.com` address
arrives here through the domain catch-all, and `davafons@hey.com` forwards here.
HEY is retired; do not use the `hey` CLI for mail.

Use `himalaya` (v2, account `zoho`, config `~/.config/himalaya/config.toml`,
password in the Keychain). Put `--json` before the subcommand for JSON output.
Message IDs are per folder; pass `-m <folder>` outside Inbox. Folders: Inbox,
Sent, Drafts, Trash, Archive, Spam, Notification (automated mail such as
verification codes).

| Need | Command |
|---|---|
| Folders | `himalaya --json mailbox list` |
| Latest mail | `himalaya --json envelope list [-s 25] [-p 2] [-m archive]` |
| Search | `himalaya --json envelope search 'from x and after 2026-11-01 order by date desc'` (`subject "q"`, `body "q"`, `to x`, `flag seen`, `not flag seen`, `and`/`or`/`()`) |
| Read | `himalaya message read <id>` (does not mark it seen; add `--seen` to mark it) |
| Thread | No thread command: search `subject "Re: …"` across Inbox and Sent |
| Draft a new message | `himalaya message compose -t a -s "subject" --body "text" --save drafts` |
| Draft a reply | `himalaya message reply <id> --body "text" --save drafts` |
| Preview without saving | Same command without `--send`/`--save`, with `--json` |
| Mark seen | `himalaya flag add --flag seen <id>` |
| Archive / delete | `himalaya message move --to archive <id>`, `himalaya message delete <id>` |

- Read, search, organize, and draft mail when requested.
- Prefer drafts (`--save drafts`) for new messages and replies. Use `--send` only when David explicitly asks to send.
- Treat sending, forwarding, deleting, moving, and flag changes as state-changing actions and confirm the exact target and content when it is not already explicit.
- Old HEY mail (2015–2026-11) is archived as MBOX in `~/Backups/hey-export-2026-11/`.

Calendar events and time blocks belong to `calendar`. Task capture and completion belong to `tasks`.
