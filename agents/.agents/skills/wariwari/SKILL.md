---
name: wariwari
description: Use the WariWari CLI to manage WariWari groups, participants, categories, transactions, and balances from an agent.
triggers:
  - wariwari
  - /wariwari
  - create wariwari event
  - create expense in wariwari
  - create payment in wariwari
  - list wariwari groups
  - show wariwari balances
invocable: true
argument-hint: "[action] [args...]"
---

# WariWari CLI

Use `wariwari` for WariWari API work. Prefer JSON output for agent workflows:

```bash
wariwari <command> --json
```

## The two rules that matter

1. **Every field on the wire is camelCase** — `lockVersion`, `amountCents`,
   `splitType`, `paidByToken`, `participantToken`, `emailAddress`,
   `groupCategoryToken`. Never send `amount_cents` or `lock_version`; they are
   rejected.
2. **The group snapshot is the read surface.** `wariwari group show TOKEN`
   returns metadata, `participants`, `groupCategories`, `transactions`,
   `netByCurrency`, `suggestedPayments` and spending totals in one payload.
   There are no separate participants, categories, or balances endpoints — the
   `participant list`, `category list`, and `balance` commands all read this
   snapshot for you.

Maps keyed by data keep their keys verbatim: `fxRates`, `spendingByCurrency`
and `netByCurrency` are keyed by ISO-4217 currency code, and `netByCurrency`'s
inner objects by participant token. Enum *values* stay snake_case
(`read_only`).

## Setup

```bash
wariwari setup
wariwari setup claude
wariwari doctor
wariwari auth status
```

API keys are created on the web account page (Account → API keys) — there is no
API route to list or mint one. Save a key with `wariwari auth login TOKEN`.
For Codex-style agents, `wariwari skill install` writes the skill to both
`~/.agents/skills/wariwari/` and the Codex skill directory.

Configuration precedence:

1. CLI flags: `--token`, `--profile`, `--api-url`, `--group`
2. Environment: `WARIWARI_TOKEN`, `WARIWARI_PROFILE`, `WARIWARI_API_URL`, `WARIWARI_GROUP`
3. Named profiles in `~/.config/wariwari/config.json`
4. Local `.wariwari.yaml`
5. Global `~/.config/wariwari/config.yaml`

## Reading

```bash
wariwari me --json
wariwari group list --json
wariwari group list --archived --take 100 --json
wariwari group show GROUP_TOKEN --json          # the full snapshot
wariwari group activity GROUP_TOKEN --json
wariwari balance GROUP_TOKEN --json
wariwari participant list GROUP_TOKEN --json
wariwari category list GROUP_TOKEN --json
wariwari transaction list GROUP_TOKEN --json
wariwari transaction show TRANSACTION_TOKEN GROUP_TOKEN --json
wariwari transaction activity TRANSACTION_TOKEN GROUP_TOKEN --json
wariwari commands --json
```

### Transactions, filtered and paged

`transaction list` reads the group's transactions newest-first. Filters combine
and narrow — a well-formed token matching nothing gives an empty page, while a
malformed date is `400 INVALID_REQUEST`.

```bash
# January expenses in the Food category that Ada paid or owes a share of
wariwari transaction list GROUP_TOKEN \
  --from 2026-01-01 --to 2026-01-31 \
  --category CATEGORY_TOKEN \
  --participant PARTICIPANT_TOKEN \
  --take 50 --json
```

Get the category and participant tokens from the snapshot's `groupCategories`
and `participants`.

### Pagination

`group list`, `transaction list`, and both activity feeds are keyset paginated.
Each response carries:

```json
{ "pagination": { "hasMore": true, "cursor": "eyJraW5kIjoia2V5c2V0In0" } }
```

Pass that value back as `--cursor` to get the next page; stop when `hasMore` is
`false`. `--take` caps at 100 and defaults to 50. The `--json` envelope also
emits a ready-to-run `next-page` breadcrumb.

### Balances

`wariwari balance GROUP_TOKEN --json` pulls the balance view out of the
snapshot:

- `netByCurrency` — currency code → participant token → signed cents. Negative
  means that participant is owed money; positive means they owe.
- `suggestedPayments` — the minimal settle-up set, each with
  `fromParticipantToken`, `toParticipantToken`, `amountCents`, `currency`.
- `spendingByCurrency`, `totalBaseCents` — group spending totals.
- `participants` — so you can turn tokens into names.

## Writing

Write commands take a JSON object via `--data` or `--data-file`. Every write
returns the refreshed group snapshot, so you never need a follow-up read.

```bash
wariwari group update GROUP_TOKEN --data '{"name":"Trip 2026","lockVersion":1}' --json
wariwari participant create GROUP_TOKEN --data '{"name":"Ada"}' --json
wariwari participant update PARTICIPANT_TOKEN GROUP_TOKEN --data '{"name":"Ada Lovelace","lockVersion":0}' --json
wariwari participant delete PARTICIPANT_TOKEN GROUP_TOKEN --json
wariwari category create GROUP_TOKEN --data '{"name":"Food","emoji":"🍜"}' --json
wariwari category update CATEGORY_TOKEN GROUP_TOKEN --data '{"name":"Food","emoji":"🍜","lockVersion":0}' --json
wariwari category delete CATEGORY_TOKEN GROUP_TOKEN --json
wariwari transaction create GROUP_TOKEN --data-file transaction-create.json --json
wariwari transaction update TRANSACTION_TOKEN GROUP_TOKEN --data-file transaction-update.json --json
wariwari transaction delete TRANSACTION_TOKEN GROUP_TOKEN --json
```

### lockVersion is required on every update

Send the `lockVersion` from the record you just read. If someone else wrote
first, the API returns `409 CONFLICT` and puts the fresh record under `current`
in the error body:

```json
{
  "code": "CONFLICT",
  "detail": "This transaction changed since you read it.",
  "status": 409,
  "current": { "token": "…", "lockVersion": 4, "amountCents": 13200 }
}
```

Recover by re-reading `current`, re-applying your change on top of it, and
retrying with the newer `lockVersion` — do not blind-retry the same body.

### Creating a group

Group creation is **session-credential only**. A developer API key (`wari_…`)
gets `403 ACCESS_DENIED`. If that happens, ask the user to create the group in
the app and give you its token.

```bash
wariwari group create --idempotency-key "$(uuidgen)" --json \
  --data '{"name":"Trip","icon":"🧳","currency":"JPY","participants":[{"name":"Ada"},{"name":"Grace"}]}'
```

`name`, `icon`, and at least one participant are required. The
`Idempotency-Key` makes a retry safe for 24 hours; reusing the key with a
different body returns `409 IDEMPOTENCY_KEY_IN_USE`.

## Expense creation workflow

1. Find the group: `wariwari group list --json`, or use the configured default.
2. Read current state: `wariwari group show GROUP_TOKEN --json`.
3. Take participant tokens from `participants` and category tokens from
   `groupCategories`. **Never invent a token.**
4. Pick `kind`: `expense` for spending, `payment` for a settle-up transfer.
5. Pick `splitType`: `equal`, `percentage`, `shares`, or `amount`.
6. Build `splits` so the `amountCents` values sum to the transaction's
   `amountCents`.
7. Create it, then read `netByCurrency` / `suggestedPayments` from the returned
   snapshot to report the new balances.

```bash
wariwari transaction create GROUP_TOKEN --json --data '{
  "kind": "expense",
  "description": "Team dinner",
  "amountCents": 12000,
  "currency": "JPY",
  "splitType": "equal",
  "date": "2026-05-23",
  "paidByToken": "7gKMjL9pPWsKaHQ4AbwS5kVj",
  "splits": [
    {"participantToken": "7gKMjL9pPWsKaHQ4AbwS5kVj", "amountCents": 4000},
    {"participantToken": "8mPNkR4qQXtLbJR5CcxT6yWa", "amountCents": 4000},
    {"participantToken": "9nQPmS5rRYuMcKS6DdyU7zXb", "amountCents": 4000}
  ]
}'
```

To edit: `wariwari transaction show TOKEN GROUP_TOKEN --json`, then send the
changed fields plus that record's `lockVersion`. Sending `splits` replaces all
existing splits.

## Errors

Failures are RFC 9457 Problem Details. Switch on `code`, show `detail`:

| Code                                              | Status | What to do                                          |
| ------------------------------------------------- | ------ | --------------------------------------------------- |
| `AUTH_CREDENTIALS_REQUIRED` / `_INVALID`          | 401    | Run `wariwari auth login TOKEN`.                    |
| `ACCESS_DENIED`                                   | 403    | Session-only action (e.g. creating a group).        |
| `INSUFFICIENT_PERMISSIONS`                        | 403    | The user lacks edit access to this group.           |
| `NOT_FOUND`                                       | 404    | Wrong token, or the record was deleted.             |
| `INVALID_REQUEST`                                 | 400    | Malformed date, cursor, or body.                    |
| `VALIDATION_FAILED`                               | 400    | Read the `errors` map (camelCase field names).      |
| `CONFLICT`                                        | 409    | Stale `lockVersion` — reconcile against `current`.  |
| `IDEMPOTENCY_KEY_IN_USE`                          | 409    | Same key, different body. Use a fresh key.          |
| `RATE_LIMIT_EXCEEDED` / `QUOTA_EXCEEDED`          | 429    | Back off; the free key quota is 50 calls/month.     |
| `IDEMPOTENCY_IN_PROGRESS`                         | 503    | A concurrent retry is running. Wait and retry.      |

Note `VALIDATION_FAILED` is a `400`, not a `422`.

## Payload templates

```bash
wariwari group example create --json
wariwari group example update --json
wariwari participant example create --json
wariwari participant example update --json
wariwari category example create --json
wariwari category example update --json
wariwari transaction example create --json
wariwari transaction example update --json
```
