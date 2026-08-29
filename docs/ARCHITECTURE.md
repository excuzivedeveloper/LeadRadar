# LeadRadar — Current Architecture

**Status:** CANONICAL  
**Last verified:** 2026-08-29  
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

Useful legacy anti-noise behavior is preserved while V2 routing and persistence
remain separate, auditable boundaries.

## Runtime identities

Current deployment uses three distinct Telegram identities:

```text
dedicated Telegram user account -> collector
owner main Telegram account     -> bot user/recipient
Telegram bot                    -> UI/delivery identity
```

The collector is independent from the bot owner allowlist and uses a separate
Telethon session.

## Runtime modes and network diagnostics

### No arguments

```bash
python -m freelancer_bot
```

Safe help-only behavior; no network runtime.

### `--bot-only`

Starts bot UI only. It does not start collector/raw ingestion, durable
matching/ingestion workers, discovery or catch-up.

### `--collector-only`

Starts authenticated collector/source-side runtime without constructing the
full ingestion runtime used by `--run`.

Important consequence:

```text
--collector-only does not collect PR #2 shadow telemetry
```

### `--check-sources`

A bounded networked Telegram diagnostic. It uses the collector user session,
takes its session lock and resolves enabled `config/sources.json` (or configured
`SOURCES_PATH`) entries through Telegram.

It does not start full ingestion/shadow runtime and requires explicit external-
work authorization.

### `--run`

Full runtime starts:

- dedicated user collector;
- Telegram bot;
- PostgreSQL-backed ingestion/durable workers;
- enabled matching/delivery components.

Catch-up, discovery, AI and legacy delivery remain independently gated by
configuration.

## Persistence boundaries

PostgreSQL is V2 source of truth for collector/source state, raw messages,
prefilter/shadow evidence, durable jobs, AI telemetry/cache, Opportunities,
SearchProfiles, matching, deliveries, feedback and entitlement state.

Alembic is the V2 schema path. Current deployment revision:

```text
20260825_0037
```

SQLite remains legacy compatibility only. `LEGACY_DELIVERY_ENABLED=false` in the
current deployment.

## Source lifecycle vs Telegram membership

These are separate conditions and must not be conflated.

### PostgreSQL source authority

`config/sources.json` is seed/diagnostic input. Runtime collector source authority
comes from PostgreSQL lifecycle/access state.

Current deployment:

```text
15 total source rows
13 APPROVED
2 CANDIDATE
```

### Telegram membership prerequisite

For live channel updates, an APPROVED source is not sufficient by itself.
The dedicated collector account must also be a Telegram participant/member of
the channel.

The project experimentally proved this distinction:

```text
0/13 memberships
+ public history readable
+ 6 natural messages during canary
=> 0 live raw callbacks
```

After joining three approved channels:

```text
membership
-> live NewMessage update
-> raw_messages
-> cheap V2 prefilter
-> legacy shadow row
```

The rollout then completed membership for all approved public sources:

```text
APPROVED_SOURCE_COUNT=13
MEMBER_AFTER_COUNT=13
NON_MEMBER_AFTER_COUNT=0
```

Therefore a deployment-ready source requires both:

```text
PostgreSQL lifecycle=APPROVED
AND
collector Telegram membership=YES
```

Do not interpret `--check-sources`/history readability as proof of live-update
readiness. Do not add automatic joining without a separately reviewed design.

## Live ingestion flow

Current steady-state flow:

```text
approved + joined Telegram source
        |
        v
dedicated Telethon collector receives NewMessage
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
personalized owner-allowlisted delivery
```

The first four live stages through shadow telemetry have now been observed with a
natural Telegram message. AI analysis and later stages have not yet been live-
validated in this deployment.

## V2 cheap prefilter vs legacy filter

The cheap V2 prefilter is intentionally high-recall and rejects only:

- empty/whitespace content;
- Telegram service events.

After cheap-prefilter pass, the full runtime evaluates legacy keyword/stop-word
`match_text()` and persists the result as observational shadow telemetry.

The legacy shadow:

- records exact config SHA and decision details;
- does not block V2 routing;
- is used to measure preserved anti-noise behavior before redesign.

Current filter snapshot used by the successful live pilot:

```text
FILTERS_SHA256=bfb6eac3f964fc6778af65be82eb55016bcf1be22d59a928df8bb098bf30a2c8
min_score=7
schema=legacy-filter-shadow.v1
```

No filter relaxation was required to prove ingestion/shadow operation.

## AI Opportunity analysis

Opportunity analysis is global per canonical raw/dedup identity, not one model
call per user.

When no analyzer is configured:

- raw ingestion/prefilter/shadow can operate;
- `opportunity.analysis.v1` jobs may remain pending;
- no provider call should occur.

The pre-AI gate has passed, but current deployment still has no AI provider key
configured. Provider/model configuration is the next separate gate.

## SearchProfiles

V2 matching uses PostgreSQL SearchProfiles. Natural-language onboarding can use a
configured OpenAI-compatible provider to produce a draft profile, which the user
confirms/activates.

The legacy `freelancer_profile.json` is a separate reply-generation profile/style
surface and must not be confused with the V2 matching SearchProfile.

## Matching and delivery

Canonical Opportunities enter deterministic/structured matching. Zero matches is
a valid result.

Personalized delivery is PostgreSQL-backed and protected by the owner allowlist.
Blocked non-allowlisted personalized deliveries are terminally suppressed.

No live lead delivery has yet been authorized in the current deployment.

## Owner-only bot boundary

With non-empty `TELEGRAM_ALLOWED_USER_IDS`, inbound authorization requires:

```text
type(sender_id) is int
sender_id > 0
sender_id in allowlist
event.is_private is True
```

No `chat_id` fallback is allowed. The centralized event wrapper applies the gate
before handler product/DB side effects. Outbound personalized/legacy delivery has
independent allowlist checks.

The collector pipeline and its channel memberships are independent from bot
allowlist state.

## Session locking

Telethon session files are bearer credentials. Collector and bot sessions use
different paths. A sidecar nonblocking lock prevents concurrent LeadRadar use of
the same session path.

Never copy, inspect, print or commit session contents.

## Discovery and audit

Web, Telegram graph/global/chat discovery and Source Audit exist in code but are
separate later-stage capabilities and remain disabled in deployment.

Their existence does not authorize execution.

## Persistent runtime

Supporting runtime code exists, but no persistent LeadRadar service is currently
authorized. Bounded successful runs are evidence gates, not daemon authorization.

Future persistent deployment preflight must verify both PostgreSQL-approved source
state and Telegram membership state.

## Observability

Prefer structured evidence containing IDs, counts, statuses and hashes rather
than live message bodies or secrets. Never deliberately log DSNs, tokens, owner
IDs, session contents or raw Telegram bodies.
