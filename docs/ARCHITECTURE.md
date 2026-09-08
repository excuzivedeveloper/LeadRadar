# LeadRadar — Current Architecture

**Status:** CANONICAL  
**Last verified:** 2026-08-31
**Implementation baseline:** `359dc17fbf4632e84b0a74f01ac201a426cf4556`

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

Alembic is the V2 schema path. The current production deployment remains at:

```text
PRODUCTION_ALEMBIC_CURRENT=20260902_0038
```

PR #15 introduces the next repository migration head:

```text
PR15_REPOSITORY_ALEMBIC_HEAD=20260904_0039
```

PR #15 is not yet merged or deployed. Before any bounded runtime shadow canary,
production must first sync the reviewed PR #15 code, apply Alembic
`20260904_0039`, and verify
`ALEMBIC_CURRENT=ALEMBIC_HEADS=20260904_0039`.

SQLite remains legacy compatibility only. `LEGACY_DELIVERY_ENABLED=false` in the
current deployment.

## Source lifecycle vs Telegram membership

These are separate conditions and must not be conflated.

### PostgreSQL source authority

`config/sources.json` is seed/diagnostic input. Runtime collector source authority
comes from PostgreSQL lifecycle/access state.

Repository head also stores an optional source language on each source row:

```text
sources.language        = ru | en | NULL
sources.language_origin = seed | discovery_query | audit | operator | NULL
sources.language_conflict = true | false
```

`language` and `language_origin` are set or cleared together. Existing
production rows are not guessed during migration; unresolved rows remain
`NULL/NULL`. A `language_conflict=true` row is deliberately unresolved after
opposing RU/EN discovery-query evidence and is valid only while
`language/language_origin` are both `NULL`. Seed-backed language is accepted
only from the explicit
`config/sources.json` `language` field. Discovery query language may provide
`discovery_query` evidence for supported `ru`/`en` candidates, while Source
Audit may provide `audit` evidence only from an exact supported
`primary_language`. Evidence is monotonic under
`operator > audit > seed > discovery_query`: stronger same-language evidence
promotes provenance, weaker evidence cannot downgrade or overwrite stronger
state, stronger contradictory evidence wins, and conflicting discovery evidence
stays unresolved until seed, audit or operator evidence resolves it.

Current deployment:

```text
15 total source rows
13 APPROVED
2 CANDIDATE
```

### Owner candidate notification aid

Repository head includes a bounded, explicit one-shot mode for notifying the
Owner about Telegram source candidates that appear fresh enough for manual
review.

Eligibility is intentionally narrow:

```text
platform=telegram
lifecycle_status=candidate
safe direct t.me channel URL available
latest Telegram message exists
latest_message_at >= now - 10 days
no prior owner_source_candidate_notifications row for (Owner, source_id)
```

The freshness check uses actual Telegram message activity fetched with the
dedicated collector account through `TelegramRequestGovernor` categories
`ENTITY_ACCESS` and `HISTORY`. Discovery timestamps, `sources.updated_at`,
provider snippets, and inferred language do not satisfy the freshness gate.
Exactly 10 days old is still eligible; older, empty, unresolvable, unsafe URL,
non-candidate, or already-attempted sources are skipped.

Candidate backlog scanning uses durable keyset progress in
`owner_source_candidate_notification_scan_state`, keyed by Owner recipient. Each
one-shot pass considers a bounded page of unnotified candidate `source_id`s
after the last scanned id, then wraps back to the beginning after exhaustion.
This prevents a stale top page from starving deeper candidates while still
allowing stale, empty, or temporarily unresolvable candidates to be reprobed on
a later pass.

For each notification attempt the probed Telegram identity and Owner URL come
from one coherent address decision: a valid source handle wins and produces both
the `get_entity` lookup and `https://t.me/<same handle>` button URL; otherwise a
valid canonical Telegram username URL is used for both. The reservation
transaction locks and rereads the source, then verifies the relevant Telegram
identity fields still match the probed address. Metadata drift suppresses the
send without writing a permanent notification marker.

Each eligible source reserves one durable row in
`owner_source_candidate_notifications` before sending a Telegram card to
`RuntimeConfig.owner_telegram_user_id`. The row is unique by
`(recipient_chat_id, source_id)`, so dedupe follows the source identity rather
than a mutable handle. `sent`, `failed`, and ambiguous attempts are terminal for
automatic notification: future passes do not retry them. Stale or empty probes
do not write a row, allowing a candidate to become fresh later and then notify
once.

Reservation outcomes are reported distinctly: true duplicate attempts increment
`ALREADY_NOTIFIED`, while source disappearance, no-longer-candidate races, and
Telegram identity changes use separate suppression counters.

The card contains source identity, language display (`RU`, `EN`, or
`не определён`), latest message date/age, candidate status, and only one URL
button to open the channel. It does not approve, reject, join, leave, delete,
score, audit, or change lifecycle state. Candidate promotion and Telegram
membership remain separate manual/reviewed gates.

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

The first four live stages through shadow telemetry have been observed with a
natural Telegram message. The bounded Opportunity Analysis path has also passed
for a fresh natural C++/HFT sample, and matching pipeline execution passed in
the PR13 repeat bounded canary. Useful owner delivery remains unproven.

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

The pre-AI gate has passed, OpenRouter implementation is server-synced, runtime
OpenRouter configuration is present for the selected Opportunity Analysis route,
and the bounded one-job Opportunity Analysis canary has passed. Full `--run`
remains inappropriate as a substitute for a narrowly scoped validation command
when a gate requires one explicit job.

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

SearchProfile preferences distinguish two language concepts:

- `preferences.languages` constrains the opportunity/content language from
  `OpportunityAnalysis.language`;
- `preferences.source_languages` constrains the global source/channel pool by
  `sources.language`.

For migrated existing profiles, `source_languages = NULL` means legacy
unconfigured behavior and does not add source-language routing. New profiles
default to `["ru", "en"]`. Explicit saved selections are only `["ru"]`,
`["en"]` or `["ru", "en"]` in canonical `ru,en` order.

## Matching and delivery

Canonical Opportunities enter deterministic/structured matching. Matching now
uses a shared local high-precision bilingual concept bridge for explicit
RU/EN technical concepts such as web development, frontend/backend, full-stack
and specific web technologies. The same bridge feeds lexical overlap, structured
matching evidence and deterministic local feature hashing; it is not a learned
multilingual embedding model and does not add broad conversational-intent
inference.

Zero matches is a valid result.

Per-profile source-language routing is a hard filter only when
`source_languages` is explicitly configured. A profile selecting only Russian
sources does not receive opportunities whose preferred source has
`source.language = en`; a profile selecting only English sources does not
receive Russian-source opportunities. If a configured profile sees a preferred
source with unresolved `source.language`, the matcher fails closed for that
profile with `source_language_unresolved`. Legacy `NULL` profile configuration
preserves pre-feature routing. Source collection remains global: approved,
active and accessible sources are still collected regardless of language.

An additional OpportunityAnalysisV2 evidence-aware matching slice is wired into
the normal fresh matching/delivery path as observational runtime shadow
instrumentation:

```text
PR14_IMPLEMENTED_IN_SHADOW=YES
PR14_EVIDENCE_RUNTIME_INSTRUMENTATION_IMPLEMENTED=YES
SHADOW_RUNTIME_WIRED=YES
SHADOW_DURABLE_PERSISTENCE=YES
PR14_PRODUCTION_MATCH_POLICY_CHANGED=NO
SHADOW_LIVE_VALIDATED=NO
SHADOW_WEIGHTS_EXPERIMENTAL=YES
SHADOW_SCORE_NOT_PRODUCTION_POLICY=YES
```

The runtime order remains:

```text
MatchingDeliveryJobProcessor
-> CandidateMatchingService.generate_matches()
-> MatchTraceRepository.persist_batch()
-> PersonalizedDeliveryService.schedule_run()
-> OpportunityEvidenceShadowRecorder.record_match_run()
```

The current matcher and delivery scheduling remain authoritative. Shadow output
cannot affect current eligibility, relevance score, rank, delivery scheduling or
durable job success. Shadow failure logs a safe structured event and fails open.

Shadow persistence is a separate append-only PostgreSQL table:

```text
opportunity_evidence_shadow_traces
schema_version=opportunity_evidence_shadow_trace.v1
shadow_version=opportunity-evidence-shadow.v2
raw_source_policy_version=opportunity-evidence-raw-source.v1
UNIQUE(match_trace_id, shadow_version)
```

The table stores current decision fields beside the independent shadow decision
and score. It stores `raw_message_id` plus `raw_content_sha256`, not the raw
Telegram message body. The JSON payload contains sanitized evidence concepts,
axes, match concepts, decision, score, independent dimensions and version flags;
it deliberately excludes raw text, contact text, Telegram usernames, email
addresses, phone numbers, transport metadata, profile semantic text and raw/profile
spans.

The V2 shadow slice records explicit raw-span evidence separately from inferred
capability/solution evidence. `RAW_EXPLICIT` evidence must be verified against
the original raw message text, not merely against AI-produced
`OpportunityAnalysis` fields. The contract keeps independent origin,
verification, confidence and polarity axes; negated, contradicted or unknown
evidence is not positive match evidence.

For example, `VK`/`ВК`/`ВКонтакте` is an explicit platform concept, while
`ИИ-менеджер в ВК` may support an explicit AI-assistant solution type and
inferred chat/lead-handling capability. It must not claim OpenAI, FastAPI,
React, Python or VK API/backend technology unless that technology is explicitly
present in the original raw message or in authoritative structured
SearchProfile fields. Free-form SearchProfile semantic text is only a low
confidence hint and cannot mint authoritative derived capabilities by itself.
Shadow matches are anti-double-counted by canonical `dimension + concept_id` and
include a generic-signal guard so generic AI/bot/automation/web/backend language
alone or in generic-only combinations is not treated as strong eligibility.

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

Profile-driven Web Discovery supports an explicit executable-query bound for
separately authorized one-shot runs:

```bash
python -m freelancer_bot.operator_cli profile-discovery run --max-queries 12
```

When the flag is omitted, legacy unbounded behavior is preserved. When provided,
the bound is applied after full strategy query generation, exact deduplication
and near-duplicate collapse, but before any Web backend call. Selection is
deterministic round-robin by discovery angle in priority order
`direct`, `buyer_habitat`, `adjacent`, followed by unknown future angles in
first-seen order. Provider observability preserves the full generated and
executable plan counts alongside the selected and actually executed counts.

## Persistent runtime

Supporting runtime code exists, but no persistent LeadRadar service is currently
authorized. Bounded successful runs are evidence gates, not daemon authorization.

Future persistent deployment preflight must verify both PostgreSQL-approved source
state and Telegram membership state.

## Observability

Prefer structured evidence containing IDs, counts, statuses and hashes rather
than live message bodies or secrets. Never deliberately log DSNs, tokens, owner
IDs, session contents or raw Telegram bodies.
