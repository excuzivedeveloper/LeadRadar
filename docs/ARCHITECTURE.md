# LeadRadar — Current Architecture

**Status:** CANONICAL  
**Last verified:** 2026-08-31
**Implementation baseline:** `d92b0446be19f391bb8f479387b27d914c081e35`

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

### `--opportunity-analysis-job-id <UUID>`

A bounded operator entrypoint for the first live Opportunity Analysis canary.
It requires one explicit durable job UUID and only accepts a claimable
`opportunity.analysis.v1` job.

It constructs the production Opportunity Analysis handler and configured
analyzer path, including PostgreSQL AI telemetry, strict local schema
validation, grounding validation, cache and canonical Opportunity persistence.

It does not construct or start:

- Telegram user client;
- Telegram bot client;
- collector/source handlers;
- raw ingestion worker;
- matching/delivery handlers;
- discovery, audit or catch-up runtime.

It exits after one selected-job processing attempt. It does not poll for or
claim another job.

### `--run`

Full runtime starts:

- dedicated user collector;
- Telegram bot;
- PostgreSQL-backed ingestion/durable workers;
- enabled matching/delivery components.

Catch-up, discovery and legacy delivery remain independently gated by
configuration. Opportunity Analysis is activated by matching provider
configuration in the full ingestion runtime; see the AI section below.

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

OpenRouter is implemented as a first-class Opportunity Analysis provider:

```text
provider=openrouter
OPENROUTER_API_KEY=<secret runtime value>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
resolved endpoint=https://openrouter.ai/api/v1/chat/completions
```

OpenRouter is not represented as TokenRouter and must keep distinct telemetry,
cache and provider identity.

The current OpenRouter scope is V2 Opportunity Analysis only. It does not add
first-class OpenRouter support for reply drafting, Source Audit, Telegram Chat
Screening, SearchProfile onboarding AI or source discovery.

Structured-output handling differs by provider family:

```text
OpenAI
-> provider-side strict json_schema response_format

non-OpenAI compatible providers, including OpenRouter
-> response_format=json_object
-> complete OpportunityAnalysis schema included in prompt
-> strict local Pydantic validation
-> grounding validation
```

Do not claim provider-side JSON Schema enforcement for OpenRouter.

When no analyzer is configured:

- raw ingestion/prefilter/shadow can operate;
- `opportunity.analysis.v1` jobs may remain pending;
- no provider call should occur.

Critical activation invariant:

```text
matching Opportunity Analysis provider key present
+ full python -m freelancer_bot --run
=> Opportunity analyzer constructed
=> opportunity.analysis.v1 handler active
=> pending analysis jobs can be claimed and provider calls can occur
```

There is no separate `OPPORTUNITY_ANALYSIS_ENABLED` switch in the current
implementation. `AI_REPLY_ENABLED=false` does not disable Opportunity Analysis;
it disables reply drafting only.

The pre-AI gate has passed, OpenRouter implementation is server-synced, and
runtime OpenRouter configuration is present for the selected Opportunity
Analysis route. No live provider call has occurred yet. The next gate is a
bounded one-job live Opportunity Analysis canary through
`--opportunity-analysis-job-id <UUID>`, not full `--run`.

With the intended canary configuration:

```text
OPPORTUNITY_ANALYSIS_MAX_OUTPUT_ATTEMPTS=1
OPPORTUNITY_ANALYSIS_FALLBACK_ENABLED=false
```

one invocation has at most one provider HTTP request path. The durable job may
finish completed, retry-queued or terminally failed according to existing job
semantics, and the command exits without reclaiming it.

## SearchProfiles

V2 matching uses PostgreSQL SearchProfiles. Natural-language onboarding can use a
configured OpenAI-compatible provider to produce a draft profile, which the user
confirms/activates.

The legacy `freelancer_profile.json` is a separate reply-generation profile/style
surface and must not be confused with the V2 matching SearchProfile.

## Matching and delivery

Canonical Opportunities enter deterministic/structured matching. Matching now
uses a shared local high-precision bilingual concept bridge for explicit
RU/EN technical concepts such as web development, frontend/backend, full-stack
and specific web technologies. The same bridge feeds lexical overlap, structured
matching evidence and deterministic local feature hashing; it is not a learned
multilingual embedding model and does not add broad conversational-intent
inference.

Zero matches is a valid result.

An additional OpportunityAnalysisV2 evidence-aware matching slice exists for
offline shadow evaluation only:

```text
OPPORTUNITY_EVIDENCE_V2_IMPLEMENTED_IN_SHADOW=YES
PRODUCTION_MATCH_POLICY_CHANGED=NO
OPPORTUNITY_EVIDENCE_V2_LIVE_VALIDATED=NO
```

The V2 shadow slice records explicit raw-span evidence separately from inferred
capability/solution evidence. For example, `VK`/`ВК`/`ВКонтакте` is an explicit
platform concept, while `ИИ-менеджер в ВК` may support an explicit AI-assistant
solution type and inferred chat/lead-handling capability. It must not claim
OpenAI, FastAPI, React, Python or VK API/backend technology unless that
technology is explicitly present in the supplied Opportunity/SearchProfile
text. Shadow matches are anti-double-counted by canonical
`dimension + concept_id` and include a generic-signal guard so generic
AI/bot/automation/web/backend language alone is not treated as strong
eligibility.

This shadow trace does not feed current hard filters, thresholds, rank scores,
delivery decisions or persisted match decisions.

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
