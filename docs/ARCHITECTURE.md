# LeadRadar — Current Architecture

**Status:** CANONICAL  
**Last verified:** 2026-08-27  
**Implementation baseline:** `f9884b196ed6a424ec69352597de66c1eeca331c`

## Purpose

LeadRadar is a Telegram freelance-opportunity discovery pipeline adapted from an
upstream Telegram lead bot. The V2 architecture separates:

- Telegram collection;
- bot UI/delivery;
- PostgreSQL persistence;
- durable jobs;
- high-recall prefiltering;
- optional AI Opportunity analysis;
- SearchProfile matching;
- personalized delivery;
- source discovery/audit.

The project intentionally preserves useful legacy anti-noise behavior while
moving V2 routing and persistence to separate, auditable boundaries.

## Runtime identities

There are three distinct Telegram identities in the current deployment design.

### Dedicated collector account

A dedicated Telegram user account owns the active Telethon user session and
reads approved source channels.

It is not the bot owner/user and is not required to be in the bot allowlist.

### Main owner account

The owner's main Telegram account is the only configured bot user/recipient in
the current private deployment.

Its numeric Telegram ID is stored only in runtime configuration and must not be
printed in reports or committed.

### Bot identity

A separate Telegram bot serves the UI and sends personalized cards.

The bot uses a separate Telethon session path from the collector.

## Runtime modes

### No arguments

```bash
python -m freelancer_bot
```

Safe help-only behavior. It must not start network runtime.

### `--bot-only`

Starts the user-facing bot UI only.

It does **not** start:

- collector user client;
- raw ingestion;
- durable ingestion/matching workers;
- source discovery;
- catch-up.

It still needs Telegram bot/API credentials and PostgreSQL.

### `--collector-only`

Starts the authenticated collector/source side without constructing the full
Telegram ingestion runtime used by `--run`.

Important consequence:

**PR #2 legacy-filter shadow telemetry is not collected by
`--collector-only`.**

### `--run`

Full runtime. It starts:

- dedicated user collector;
- Telegram bot;
- PostgreSQL-backed ingestion runtime/durable workers;
- matching/delivery components that are enabled/configured.

Catch-up, discovery, AI and legacy delivery remain separately controlled by
configuration and are not implied merely by choosing `--run`.

## Persistence boundaries

### PostgreSQL — V2 source of truth

V2 state includes, among other things:

- collector accounts and source access;
- sources/lifecycle/audit evidence;
- raw messages;
- prefilter results;
- shadow evaluations;
- durable jobs;
- AI telemetry/cache;
- canonical Opportunities;
- SearchProfiles;
- match decisions/traces;
- personalized deliveries/actions;
- feedback;
- subscription/entitlement evidence.

Alembic is the schema change path.

Current deployment migration head:

```text
20260825_0037
```

### SQLite — legacy compatibility only

SQLite remains for legacy V1 compatibility surfaces. It is not the V2 source of
truth.

`LEGACY_DELIVERY_ENABLED=false` in the current deployment.

Do not migrate V2 state back into SQLite or treat SQLite as current product
storage.

## Source lifecycle

`config/sources.json` is repository seed/diagnostic input.

At runtime the collector binds its real Telegram account to PostgreSQL and loads
only sources allowed by the PostgreSQL lifecycle/access model.

Current deployment seed state:

```text
15 total
13 approved/enabled
2 candidate/disabled
```

The 13 enabled sources were validated as accessible by the dedicated collector.

Discovery or audit must not bypass lifecycle approval.

## Live ingestion flow

Conceptually:

```text
approved Telegram source
        |
        v
dedicated Telethon collector
        |
        v
raw_messages + telegram.raw_message.v1 durable job
        |
        v
RawMessagePrefilterProcessor
        |
        +--> cheap V2 prefilter result
        |
        +--> legacy match_text() shadow evaluation
        |      schema=legacy-filter-shadow.v1
        |      exact filters.json SHA recorded
        |
        v
opportunity.analysis.v1 durable job
        |
        v
optional Opportunity analyzer
        |
        v
canonical Opportunity
        |
        v
matching against active SearchProfiles
        |
        v
personalized delivery job
        |
        v
owner-allowlisted Telegram bot send
```

## V2 cheap prefilter vs legacy filter

These must not be conflated.

### Cheap V2 prefilter

Designed for high recall. It rejects only:

- empty/whitespace content;
- Telegram service events.

All other normal text remains eligible for downstream analysis.

### Legacy filter shadow

After the cheap V2 prefilter passes, the current full ingestion runtime evaluates
the legacy keyword/stop-word `match_text()` logic and records the result in
PostgreSQL.

The legacy shadow:

- is observational;
- records exact config SHA and decision details;
- does not block V2 routing;
- exists so the project can compare accumulated anti-noise behavior against the
  V2 pipeline before redesigning the legacy matcher.

## AI Opportunity analysis

Opportunity analysis is global per canonical raw/dedup identity, not one model
call per user.

When a compatible provider is configured, analysis can classify and materialize
canonical Opportunities. Exact compatible analysis cache entries can be reused.

When no Opportunity analyzer is configured:

- raw ingestion/prefilter/shadow can still operate;
- `opportunity.analysis.v1` jobs may remain pending;
- no provider call should occur.

The current deployment intentionally has no AI keys configured.

## SearchProfiles

V2 user matching is based on PostgreSQL SearchProfiles.

Natural-language onboarding can use a configured OpenAI-compatible provider to
produce a draft profile, which the user confirms/activates.

Multiple profiles per user are supported with ownership checks.

The legacy `freelancer_profile.json` is a separate reply-generation style/profile
surface and must not be confused with the V2 SearchProfile used for matching.

See `docs/profile-setup.md`.

## Matching and delivery

Canonical Opportunities enter the matching/delivery path.

Matching is deterministic/structured with optional semantic data and explicit
thresholds. Zero matches is a valid result.

Personalized delivery is per recipient and PostgreSQL-backed.

The current private deployment adds defense in depth:

```text
allowlist non-empty
AND recipient not allowlisted
=> no Telegram send
```

Blocked personalized deliveries are terminally suppressed rather than retried
forever.

## Owner-only bot boundary

Configuration:

```text
TELEGRAM_ALLOWED_USER_IDS=<comma-separated positive Telegram user IDs>
```

An empty value preserves the repository's backward-compatible public-bot
behavior.

With a non-empty allowlist, inbound bot authorization requires:

```text
type(sender_id) is int
sender_id > 0
sender_id in allowlist
event.is_private is True
```

No `chat_id` fallback is allowed for authorization.

The centralized bot-event wrapper executes this gate before handler product/DB
side effects.

This boundary applies to normal messages, commands, navigation/free text and
callbacks. Outbound personalized and legacy delivery have independent allowlist
checks.

The collector pipeline is unaffected by the bot allowlist.

## Session locking

Telethon session files are bearer credentials.

Collector and bot sessions use different paths. A sidecar nonblocking lock
prevents concurrent LeadRadar processes from using the same session path.

Never copy, inspect, print or commit session contents.

## Discovery and audit

The repository contains Web, Telegram graph/global/chat discovery and Source
Audit capabilities.

These are separate operational stages and are currently disabled in the live
deployment.

Their existence in code does not authorize their execution.

## Observability

Structured logs and operator commands are designed to expose identifiers,
counts and bounded evidence rather than raw message bodies or secrets.

Operators must still treat logging as a security boundary: do not deliberately
print DSNs, tokens, owner IDs, session contents or live Telegram bodies.
