# LeadRadar — Accepted Decisions

**Status:** CANONICAL  
**Last verified:** 2026-08-27

These decisions explain why the current architecture and execution order look
the way they do. Reversing one should be an explicit reviewed decision, not an
incidental refactor.

## D-001 — Preserve useful upstream anti-noise behavior

LeadRadar is a fork/adaptation, not a clean-sheet rewrite.

The upstream Telegram filter accumulated useful anti-spam/anti-noise behavior.
Codence adaptation changed positive signal/profile configuration while
deliberately preserving most stop-word behavior.

Known matcher imperfections are tolerated until measured with real shadow
evidence.

**Consequence:** do not replace the legacy filter wholesale merely because the
V2 pipeline exists.

## D-002 — V2 uses PostgreSQL as source of truth

V2 users, SearchProfiles, sources, raw messages, durable jobs, Opportunities,
matching and personalized delivery are PostgreSQL-backed.

SQLite remains legacy compatibility storage only.

**Consequence:** new V2 state or schema belongs in PostgreSQL/Alembic, not in
SQLite.

## D-003 — Dedicated collector account is separate from the owner

The active Telethon collector uses a dedicated Telegram account.

The owner's main account is the bot user/recipient.

**Reason:** reduce operational risk to the owner's main Telegram account and
separate collector session risk from bot ownership/recovery.

**Consequence:** do not switch collection back to the main account without a new
explicit decision.

## D-004 — Bot is private to an explicit allowlist

Current deployment uses exactly one allowlisted user: the owner.

Inbound authorization requires both valid allowlisted sender identity and
private 1:1 context. Outbound delivery has a separate allowlist boundary.

**Reason:** BotFather cannot make a one-user security boundary, and hiding a bot
username is not access control.

**Consequence:** `TELEGRAM_TARGET_CHAT_ID` alone is not sufficient authorization.

## D-005 — Source JSON is seed input, PostgreSQL is runtime authority

`config/sources.json` is useful for repository configuration, seed import and
diagnostics.

The collector runtime must use PostgreSQL source lifecycle/access state.

**Reason:** auditable lifecycle, collector access control and no permissive JSON
fallback.

## D-006 — Legacy filter runs in shadow, not as the V2 gate

The V2 cheap prefilter is high-recall. The legacy keyword/stop-word filter is
evaluated after a cheap-prefilter pass and persisted as observational telemetry.

**Reason:** collect evidence before deciding how much legacy anti-noise logic
should influence later V2 behavior.

**Consequence:** `--collector-only` is insufficient to collect PR #2 shadow
evidence; bounded full `--run` is required.

## D-007 — Do not use catch-up to manufacture canary evidence

Current live validation uses only naturally arriving new Telegram messages.

**Reason:** the first goal is to prove steady-state live dispatch and shadow
behavior without adding historical load, duplicate ambiguity or unexpected
delivery/AI cost.

**Consequence:** a no-message canary is inconclusive, not a reason to
automatically set `SEND_CATCH_UP=true`.

## D-008 — AI is a separate gate

AI code exists, but current deployment has no AI key configured.

**Reason:** first prove collection/prefilter/shadow safety, then choose a
provider/model and budget explicitly.

**Consequence:** no AI provider should be called during shadow canaries.

## D-009 — Bounded validation precedes persistent runtime

Every external-work stage is first tested in a bounded foreground window with
explicit stop conditions.

**Reason:** reduce Telegram/account/cost/shared-server risk and produce
reproducible evidence.

**Consequence:** a successful bounded run does not authorize a daemon/systemd
deployment.

## D-010 — LeadRadar is isolated on a shared server

LeadRadar owns its checkout, runtime directory, PostgreSQL container/network/
volume and project-local Python tooling.

**Consequence:** LeadRadar work must not modify unrelated projects, services,
global Python, firewall or system time.

## D-011 — Rotate any exposed credential before continuing

If a bot token, DB credential, session credential, provider key or other bearer
secret appears in chat/log output, it is treated as compromised and replaced
before the next live stage.

**Consequence:** historical exposed values are invalid; current replacement
values must never be copied into documentation.
