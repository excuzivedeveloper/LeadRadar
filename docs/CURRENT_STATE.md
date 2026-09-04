# LeadRadar — Current State

**Status:** CANONICAL  
**Snapshot date:** 2026-08-31
**Implementation baseline:** `d92b0446be19f391bb8f479387b27d914c081e35`
**Current deployed repository head:** `d92b0446be19f391bb8f479387b27d914c081e35`

## Executive status

LeadRadar has completed the **pre-AI live ingestion/shadow gate**.

Current gate status:

```text
OWNER_ONLY_BOT_READY=YES
DEDICATED_COLLECTOR_READY=YES
SOURCE_CATALOG_READY=YES
COLLECTOR_MEMBERSHIP_READY=YES
POSTGRES_READY=YES
SHADOW_LIVE_EVIDENCE=YES
OPENROUTER_IMPLEMENTATION_READY=YES
OPENROUTER_RUNTIME_CONFIGURED=YES
OPENROUTER_API_KEY_CONFIGURED=YES
OPPORTUNITY_ANALYSIS_PROVIDER=openrouter
OPPORTUNITY_ANALYSIS_MODEL=minimax/minimax-m3:free
PROVIDER_LIVE_CALLS=0
LIVE_AI_ANALYSIS_VALIDATED=NO
READY_FOR_OPENROUTER_CONFIGURATION=COMPLETE
READY_FOR_BOUNDED_AI_ANALYSIS=YES
PERSISTENT_RUNTIME_AUTHORIZED=NO
```

The exact next execution stage after this one-shot implementation is merged and
server-synced is:

```text
BOUNDED_ONE_SHOT_OPENROUTER_OPPORTUNITY_ANALYSIS
```

OpenRouter implementation and runtime configuration are present, but no live
provider call has occurred. Discovery, catch-up, legacy delivery and persistent
runtime remain disabled.

## Repository and migration state

Application implementation baseline:

```text
d92b0446be19f391bb8f479387b27d914c081e35
```

Current server repository head:

```text
d92b0446be19f391bb8f479387b27d914c081e35
```

Runtime/tooling baseline:

```text
Python=3.14.7
uv=0.12.2
PostgreSQL=18.x
Alembic head=20260825_0037
```

The current migration set includes:

```text
message_prefilter_shadow_evaluations
schema=legacy-filter-shadow.v1
```

Relevant merged adaptation milestones:

- PR #1 — Codence profile/filter adaptation while preserving upstream
  anti-noise behavior.
- PR #2 — V2 prefilter legacy-filter shadow telemetry.
- PR #3 — owner-only Telegram bot allowlist with private-chat enforcement and
  outbound delivery defense in depth.
- PR #4 — canonical self-contained documentation for new agents.
- PR #6 — first-class OpenRouter Opportunity Analysis provider support.

PR #6 was independently forensically reviewed with no findings, merged, and
server-synced to the same head. Offline validation passed:

```text
OPENROUTER_UNIT_TESTS=PASS
FULL_UNITTEST_DISCOVERY=PASS
FULL_TEST_COUNT=582
PY_COMPILE=PASS
CHECK_CONFIG=PASS
```

Server implementation sync report SHA-256:

```text
89decdcf40c3486d5cd51571ab2ab27d99049abb0d2158be602d11188bd4b369
```

## Completed deployment milestones

### Isolated server foundation

Completed:

- checkout at `/opt/leadradar/LeadRadar`;
- project-local Python/venv and uv tooling;
- isolated PostgreSQL container;
- Alembic at `20260825_0037`;
- no persistent LeadRadar application service.

### Telegram identity separation

Accepted deployment architecture:

```text
dedicated Telegram account -> collector
main owner Telegram account -> bot user/recipient
Telegram bot -> separate bot identity
```

The old main-account collector session is not the active collector path.

### Source catalog and collector membership

Repository seed:

```text
TOTAL=15
ENABLED=13
DISABLED=2
```

PostgreSQL runtime state:

```text
ROWS=15
APPROVED=13
CANDIDATE=2
```

The 13 approved public sources are now also Telegram memberships of the
dedicated collector account:

```text
APPROVED_SOURCE_COUNT=13
MEMBER_AFTER_COUNT=13
NON_MEMBER_AFTER_COUNT=0
COLLECTOR_MEMBERSHIP_ROLLOUT=COMPLETE
COLLECTOR_DEPLOYMENT_READY=YES
```

This membership is a deployment prerequisite for live `NewMessage` delivery.
Being able to resolve/read a public channel history is **not** sufficient proof
that Telegram will deliver live channel updates to the collector account.

`config/sources.json` remains seed/diagnostic input. PostgreSQL lifecycle/access
state remains runtime source authority.

### Bot and owner-only access

Completed:

- bot session authorized;
- owner main account successfully used `/start`;
- `TELEGRAM_ALLOWED_USER_IDS` contains exactly one owner entry;
- private owner interaction works;
- group/supergroup interaction is blocked even for the owner;
- missing sender identity fails closed;
- personalized/legacy delivery boundaries reject recipients outside allowlist;
- collector identity is independent from the bot allowlist.

The actual owner numeric ID is intentionally absent from documentation.

## Current runtime safety flags

Expected deployment state remains:

```text
SEND_CATCH_UP=false
LEGACY_DELIVERY_ENABLED=false

SOURCE_DISCOVERY_ENABLED=false
SOURCE_AUDIT_ENABLED=false
SOURCE_GRAPH_DISCOVERY_ENABLED=false
TELEGRAM_CHAT_DISCOVERY_ENABLED=false

AI_REPLY_ENABLED=false

OPENAI_API_KEY_CONFIGURED=NO
DEEPSEEK_API_KEY_CONFIGURED=NO
TOKENROUTER_API_KEY_CONFIGURED=NO
OPENROUTER_API_KEY_CONFIGURED=YES
```

There is no persistent LeadRadar app/bot/collector process.

## Current filter/source snapshots

Current filter snapshot:

```text
FILTERS_PATH=config/filters.json
FILTERS_SHA256=bfb6eac3f964fc6778af65be82eb55016bcf1be22d59a928df8bb098bf30a2c8
MIN_SCORE=7
KEYWORDS=119
STOP_WORDS=71
```

Repository source JSON snapshot previously verified on server:

```text
SOURCES_SHA256=cd920e87954a864d0720088f7a3b13fe182807f27f2a4d253b346e84c525c40c
TOTAL=15
ENABLED=13
DISABLED=2
```

No filter change was needed to obtain live raw/prefilter/shadow evidence.

## V2 prefilter and legacy shadow semantics

The V2 cheap prefilter intentionally has high recall. It rejects only:

- service-event messages;
- blank/whitespace content.

For a message that passes the cheap prefilter, full runtime evaluates legacy
`match_text()` **in shadow only** and stores:

- accepted;
- score;
- matched keywords;
- rejected-by reason;
- min score;
- exact filter config SHA-256;
- schema version `legacy-filter-shadow.v1`.

The shadow result does not decide whether V2 analysis work is routed.

Known legacy matcher substring behavior remains intentionally preserved until
more shadow data justifies a narrow evidence-backed change.

## OpenRouter Opportunity Analysis state

First-class OpenRouter support is implemented only for V2 Opportunity Analysis.
It is not current first-class support for reply drafting, Source Audit,
Telegram Chat Screening, SearchProfile onboarding AI or source discovery.

Selected initial route for the next AI gate:

```text
OPPORTUNITY_ANALYSIS_PROVIDER=openrouter
OPPORTUNITY_ANALYSIS_MODEL=minimax/minimax-m3:free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
RESOLVED_CHAT_COMPLETIONS_ENDPOINT=https://openrouter.ai/api/v1/chat/completions
OPPORTUNITY_ANALYSIS_FALLBACK_ENABLED=false
```

The route is selected for the first bounded Opportunity Analysis path, not a
permanent provider lock-in. `minimax/minimax-m3:free` availability, rate limits
and pricing are external and must be reverified immediately before
configuration/live validation.

Current runtime state:

```text
OPENROUTER_IMPLEMENTATION_READY=YES
OPENROUTER_RUNTIME_CONFIGURED=YES
OPENROUTER_API_KEY_CONFIGURED=YES
PROVIDER_LIVE_CALLS=0
LIVE_AI_ANALYSIS_VALIDATED=NO
READY_FOR_OPENROUTER_CONFIGURATION=COMPLETE
READY_FOR_BOUNDED_AI_ANALYSIS=YES
```

Important runtime invariant: the current implementation has no separate
`OPPORTUNITY_ANALYSIS_ENABLED` switch. Once the matching Opportunity Analysis
provider key is configured, starting full `python -m freelancer_bot --run` can
construct the analyzer, activate the `opportunity.analysis.v1` handler, claim
existing pending analysis jobs and make provider calls. `AI_REPLY_ENABLED=false`
does not disable Opportunity Analysis; it gates reply drafting only.

This branch adds the production-safe operator entrypoint for the first bounded
AI canary:

```bash
python -m freelancer_bot --opportunity-analysis-job-id <UUID>
```

It requires one explicit durable job UUID, accepts only claimable
`opportunity.analysis.v1` jobs, constructs only the Opportunity Analysis handler
and exits after one selected-job processing attempt. It does not start Telegram,
collector, discovery, catch-up, matching or delivery runtime. With
`OPPORTUNITY_ANALYSIS_MAX_OUTPUT_ATTEMPTS=1` and
`OPPORTUNITY_ANALYSIS_FALLBACK_ENABLED=false`, one invocation can make at most
one provider request.

## Live validation history

### 600-second initial canary

Result:

```text
NEW_RAW_MESSAGES=0
NEW_PREFILTER_RESULTS=0
NEW_SHADOW_EVALUATIONS=0
CANARY_RESULT=INCONCLUSIVE_NO_MESSAGES
```

### 3600-second follow-up canary

Natural Telegram traffic was later shown to have existed during this window,
but LeadRadar still received no live updates:

```text
TOTAL_MESSAGES_DURING_CANARY=6
SOURCES_WITH_MESSAGES_DURING_CANARY=3
NEW_RAW_MESSAGES=0
```

Investigation established:

```text
DEDICATED_COLLECTOR_PARTICIPANT_IN_APPROVED_SOURCES=0/13
FILTER_THRESHOLD_CAUSED_ZERO_RAW_MESSAGES=NO
```

Public-history accessibility had created a false readiness signal: the account
could resolve/read sources but was not a channel participant, so live updates
were not delivered.

Investigation report SHA-256:

```text
cf5f14807005319ddf4862c36746904670ca04a1e9aa69a480650a792865eb12
```

### Controlled membership pilot

The collector joined three approved public sources. A natural message then
passed the real live path in 306 seconds:

```text
PILOT_SOURCE_COUNT=3
JOINED_PILOT_SOURCE_COUNT=3
ACTUAL_CANARY_SECONDS=306
EARLY_STOP_USED=YES

NEW_RAW_MESSAGES=1
NEW_PREFILTER_RESULTS=1
NEW_SHADOW_EVALUATIONS=1
NEW_OPPORTUNITIES=0
NEW_DELIVERIES=0

SHADOW_SCHEMA_MATCH=YES
SHADOW_FILTER_SHA_MATCH=YES
AI_PROVIDER_CALLS=0

MEMBERSHIP_HYPOTHESIS=CONFIRMED
COLLECTOR_MEMBERSHIP_IS_DEPLOYMENT_PREREQUISITE=YES
CODE_FIX_REQUIRED=NO_EVIDENCE
VERDICT=MEMBERSHIP_PILOT_PASS
```

Pilot report SHA-256:

```text
f60769f6dcfbe65b7094ba7fba901fea9bc1e9a2278481c49265f83a9c50c623
```

### Approved-source membership rollout

The remaining 10 approved public sources were joined successfully:

```text
APPROVED_SOURCE_COUNT=13
NEW_JOIN_REQUESTS=10
NEW_JOIN_SUCCESS_COUNT=10
NEW_JOIN_FAILURE_COUNT=0
MEMBER_AFTER_COUNT=13
NON_MEMBER_AFTER_COUNT=0
COLLECTOR_MEMBERSHIP_ROLLOUT=COMPLETE
COLLECTOR_DEPLOYMENT_READY=YES
```

Rollout report SHA-256:

```text
dfbf1d19b29963c43e01eb9512e6817343a2274182be4c0d562466f0898cec5e
```

No additional full-runtime canary was required for the rollout because the pilot
already proved membership -> live update -> raw -> prefilter -> shadow.

## Implemented vs currently live-validated

| Capability | Implemented | Current deployment/live evidence |
| --- | --- | --- |
| Safe CLI/config | yes | validated |
| PostgreSQL V2 + migrations | yes | validated |
| Dedicated collector identity | yes | validated |
| PostgreSQL source lifecycle/catalog | yes | 15 rows; 13 approved |
| Collector membership prerequisite | deployment state | validated; 13/13 joined |
| Raw Telegram persistence | yes | **live-validated** |
| Cheap V2 prefilter | yes | **live-validated** |
| Legacy-filter shadow telemetry | yes | **live-validated** |
| OpenRouter Opportunity provider | yes | offline tests and server sync passed; runtime configured |
| OpenRouter runtime configuration | n/a | **configured; zero live calls** |
| Opportunity AI analysis | yes | no live provider call/model response validated |
| Canonical Opportunities/dedup | yes | not live-validated with real AI output |
| SearchProfiles/onboarding | yes | owner UI exists; AI onboarding not enabled |
| Matching | yes; includes local high-precision RU/EN technical concept bridge | not live-validated end to end |
| Personalized delivery | yes | owner-only boundary validated; no live lead delivery yet |
| Owner-only bot access | yes | owner positive path live-validated |
| Source discovery/audit | yes | disabled |
| Persistent runtime/service | supporting code exists | **not authorized/deployed** |

## Credentials and incidents

No current secret value belongs in Git, docs, issue comments or chat transcripts.
Credentials exposed during earlier setup/diagnostic work were rotated before
continuing. Historical values are invalid and must not be reused.

## What remains

The ingestion/shadow gate is complete. Remaining ordered gates are:

1. merge and server-sync the one-shot Opportunity Analysis command;
2. bounded one-job live OpenRouter Opportunity analysis;
3. owner SearchProfile/onboarding validation for the chosen AI route;
4. bounded matching + personalized delivery to the owner;
5. later decision on legacy-filter tuning from accumulated shadow evidence;
6. later source discovery/audit rollout if desired;
7. persistent runtime only after bounded end-to-end validation.

The authoritative order is in `docs/ACTIVE_PLAN.md`.
