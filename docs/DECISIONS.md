# LeadRadar — Accepted Decisions

**Status:** CANONICAL  
**Last verified:** 2026-08-30

These decisions explain why the current architecture and execution order look
the way they do. Reversing one should be an explicit reviewed decision, not an
incidental refactor.

## D-001 — Preserve useful upstream anti-noise behavior

LeadRadar is a fork/adaptation, not a clean-sheet rewrite.

The upstream Telegram filter accumulated useful anti-spam/anti-noise behavior.
Codence adaptation changed positive signal/profile configuration while
preserving most stop-word behavior.

Known matcher imperfections are tolerated until enough real shadow evidence
supports a narrow change.

**Consequence:** do not replace the legacy filter wholesale merely because the
V2 pipeline exists.

## D-002 — V2 uses PostgreSQL as source of truth

V2 users, SearchProfiles, sources, raw messages, durable jobs, Opportunities,
matching and personalized delivery are PostgreSQL-backed.

SQLite remains legacy compatibility storage only.

**Consequence:** new V2 state/schema belongs in PostgreSQL/Alembic, not SQLite.

## D-003 — Dedicated collector account is separate from the owner

The active Telethon collector uses a dedicated Telegram account. The owner's
main account is the bot user/recipient.

**Reason:** reduce operational risk to the owner's main account and separate
collector session risk from bot ownership/recovery.

**Consequence:** do not switch collection back to the main account without a new
explicit decision.

## D-004 — Bot is private to an explicit allowlist

Current deployment uses exactly one allowlisted user: the owner.

Inbound authorization requires valid allowlisted sender identity and private 1:1
context. Outbound delivery has a separate allowlist boundary.

**Reason:** BotFather cannot create a one-user application authorization
boundary, and hiding a username is not access control.

## D-005 — Source JSON is seed input, PostgreSQL is runtime authority

`config/sources.json` is useful for repository configuration, seed import and
diagnostics. Collector runtime source lifecycle/access authority is PostgreSQL.

**Reason:** auditable lifecycle and no permissive JSON fallback.

## D-006 — Legacy filter runs in shadow, not as the V2 gate

The V2 cheap prefilter is high-recall. Legacy keyword/stop-word `match_text()` is
evaluated after cheap-prefilter pass and persisted as observational telemetry.

**Consequence:** `--collector-only` is insufficient to collect PR #2 shadow
evidence; bounded full `--run` is required.

## D-007 — Do not use catch-up to manufacture canary evidence

Current live validation uses naturally arriving new Telegram messages.

**Reason:** prove steady-state live dispatch/shadow behavior without historical
load, duplicate ambiguity or unexpected downstream cost.

**Consequence:** a no-message canary is inconclusive, not permission to set
`SEND_CATCH_UP=true`.

## D-008 — AI is a separate gate

AI code exists, but pre-AI collection/prefilter/shadow validation must pass first.
That gate is now complete; provider/model/key configuration is the next separate
stage.

**Consequence:** configuration readiness and first live AI provider call remain
separate authorizations.

## D-009 — Bounded validation precedes persistent runtime

Every external-work stage is first exercised in a bounded foreground task with
explicit stop conditions.

**Consequence:** a successful bounded run does not authorize daemon/systemd
operation.

## D-010 — LeadRadar is isolated on a shared server

LeadRadar owns its checkout, runtime directory, PostgreSQL container/network/
volume and project-local Python tooling.

**Consequence:** LeadRadar work must not modify unrelated projects, services,
global Python, firewall or system time.

## D-011 — Rotate any exposed credential before continuing

If a bot token, DB credential, session credential, provider key or other bearer
secret appears in chat/log output, it is treated as compromised and replaced
before the next live stage.

**Consequence:** historical exposed values are invalid; replacements must never
be copied into documentation.

## D-012 — Telegram membership is a collector deployment prerequisite

A PostgreSQL-approved public source being resolvable/readable does **not** prove
that Telegram will deliver live channel updates to the dedicated collector.

This was experimentally established:

```text
collector membership=0/13
natural messages during canary=6
live raw callbacks=0
```

After joining three approved channels, a natural message traversed:

```text
live NewMessage
-> raw_messages
-> cheap prefilter
-> legacy shadow
```

The remaining approved public sources were then joined successfully, producing:

```text
approved sources=13
collector memberships=13
non-members=0
```

**Decision:** deployment readiness for a monitored source requires both:

```text
PostgreSQL lifecycle=APPROVED
AND
collector Telegram membership=YES
```

**Consequence:** source seeding/access checks and Telegram membership
provisioning are separate operations. `--check-sources` is not a membership or
live-update readiness proof.

Automatic join behavior is **not** accepted by this decision. Adding auto-join
would introduce new external side effects/rate-limit risk and requires its own
reviewed design.

## D-013 — First live Opportunity route uses first-class OpenRouter identity

The selected initial live Opportunity Analysis route is:

```text
provider=openrouter
model=minimax/minimax-m3:free
```

OpenRouter must be represented as `openrouter` in configuration, telemetry and
cache identity. It must not masquerade as TokenRouter or borrow TokenRouter
credentials.

This decision is for the initial bounded Opportunity Analysis route only; it is
not a permanent provider lock-in and it does not automatically extend OpenRouter
support to SearchProfile onboarding, Source Audit, Telegram Chat Screening,
reply drafting or source discovery.

`minimax/minimax-m3:free` availability, pricing and free-tier/rate limits are
external provider facts and must be reverified before configuration/live
validation when relevant.

Configuration and the first live provider call are separate gates. In the
current implementation, once the matching Opportunity Analysis key is present,
full `--run` can construct the analyzer, activate the `opportunity.analysis.v1`
handler, claim pending jobs and make provider calls. `AI_REPLY_ENABLED=false`
does not disable Opportunity Analysis.
