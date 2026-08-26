# LeadRadar — Current State

**Status:** CANONICAL  
**Snapshot date:** 2026-08-27  
**Implementation baseline:** `f9884b196ed6a424ec69352597de66c1eeca331c`  
**Deployment baseline:** `f9884b196ed6a424ec69352597de66c1eeca331c`

> A docs-only synchronization commit may make repository `HEAD` newer than the
> implementation baseline above. Verify subsequent code changes before assuming
> this snapshot is still complete.

## Executive status

LeadRadar is in **pre-AI live validation**.

The repository already contains the V2 PostgreSQL pipeline, Opportunity
analysis, SearchProfiles, matching, personalized delivery, source discovery and
other later-stage code, but the current deployment is intentionally being
enabled in bounded gates rather than all at once.

Current gate status:

```text
OWNER_ONLY_BOT_READY=YES
DEDICATED_COLLECTOR_READY=YES
SOURCE_CATALOG_READY=YES
POSTGRES_READY=YES
SHADOW_LIVE_EVIDENCE=NO
READY_FOR_AI_SETUP=NO
PERSISTENT_RUNTIME_AUTHORIZED=NO
```

The exact next execution stage is:

```text
FOLLOWUP_BOUNDED_SHADOW_EVIDENCE
```

AI, discovery, catch-up and persistent runtime remain disabled until that gate
passes.

## Repository and migration state

Implementation baseline:

```text
main=f9884b196ed6a424ec69352597de66c1eeca331c
```

That merge is PR #3, `feat: restrict Telegram bot to allowed users`.

Runtime/tooling baseline:

```text
Python=3.14.7
uv=0.12.2
PostgreSQL=18.x
Alembic head=20260825_0037
```

The current migration added:

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

## Completed deployment milestones

### Isolated server foundation

Completed:

- isolated checkout at `/opt/leadradar/LeadRadar`;
- project-local Python/venv and uv cache;
- isolated PostgreSQL 18.4 Alpine container;
- Alembic upgraded to current head;
- no LeadRadar persistent application service created.

### Telegram identity separation

The accepted deployment architecture is:

```text
dedicated Telegram account -> collector
main owner Telegram account -> bot user/recipient
Telegram bot -> separate bot identity
```

The old main-account user session is not the active collector session.

### Source catalog

Repository seed:

```text
TOTAL=15
ENABLED=13
DISABLED=2
```

Server PostgreSQL state after seed:

```text
ROWS=15
APPROVED=13
CANDIDATE=2
```

All 13 enabled public sources were successfully resolved/accessed by the
dedicated collector during validation.

`config/sources.json` is seed/diagnostic input. The full runtime loads its
approved source snapshot from PostgreSQL.

### Bot and owner-only access

Completed:

- bot token configured and bot session authorized;
- owner main account successfully used `/start`;
- `TELEGRAM_ALLOWED_USER_IDS` is configured with exactly one positive owner ID;
- owner private 1:1 interaction works;
- group/supergroup interaction is blocked even for the owner;
- missing sender identity fails closed;
- personalized and legacy delivery boundaries reject recipients outside the
  configured allowlist;
- the collector is not constrained by the bot allowlist.

The actual numeric owner ID is intentionally not recorded in repository
documentation.

## Current runtime safety flags

Current deployment is expected to remain:

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
```

There is no persistent LeadRadar app/bot/collector process.

## Current filter/source snapshots

Current filter file verified during the first full-runtime canary:

```text
FILTERS_PATH=config/filters.json
FILTERS_SHA256=bfb6eac3f964fc6778af65be82eb55016bcf1be22d59a928df8bb098bf30a2c8
MIN_SCORE=7
KEYWORDS=119
STOP_WORDS=71
```

Current source JSON content snapshot previously verified on server:

```text
SOURCES_SHA256=cd920e87954a864d0720088f7a3b13fe182807f27f2a4d253b346e84c525c40c
TOTAL=15
ENABLED=13
DISABLED=2
```

Do not change either snapshot during the current shadow-evidence gate without a
new review.

## V2 prefilter and legacy shadow semantics

The V2 cheap prefilter intentionally has high recall. It rejects only:

- service-event messages;
- blank/whitespace content.

For a message that passes the cheap V2 prefilter, the runtime evaluates the
legacy `match_text()` filter **in shadow only** and stores:

- accepted;
- score;
- matched keywords;
- rejected-by reason;
- min score;
- exact filter config SHA-256;
- schema version `legacy-filter-shadow.v1`.

The shadow result does not decide whether V2 analysis work is routed.

A known legacy matcher limitation is intentionally preserved: substring-based
stop-word matching can reject legitimate text in some cases (for example a
short stop token occurring inside another word). Do not redesign this matcher
until live shadow evidence justifies a narrow change.

## First bounded full-runtime canary

Date: 2026-08-27.

The exact full runtime was started for 600 seconds with owner-only access,
catch-up/discovery/AI/legacy delivery disabled.

Result:

```text
FULL_RUNTIME_STARTED=YES
FULL_RUNTIME_EXIT=GRACEFUL
RUNTIME_ERROR=NONE

NEW_RAW_MESSAGES=0
NEW_PREFILTER_RESULTS=0
NEW_SHADOW_EVALUATIONS=0
NEW_OPPORTUNITY_ANALYSIS_JOBS=0
NEW_OPPORTUNITIES=0
NEW_DELIVERIES=0

AI_PROVIDER_CALLS=0
DISCOVERY_RAN=NO
CATCH_UP_RAN=NO
LEGACY_DELIVERY_RAN=NO

CANARY_RESULT=INCONCLUSIVE_NO_MESSAGES
READY_FOR_AI_SETUP=NO
```

Interpretation: runtime safety/startup/shutdown were validated, but no natural
source message arrived during the 10-minute window. Therefore there is still no
live proof of the raw -> V2 prefilter -> legacy shadow path. This is not a
runtime failure.

## Implemented vs currently live-validated

| Capability | Implemented in code | CI/test evidence | Current deployment/live evidence |
| --- | --- | --- | --- |
| Safe CLI modes/config | yes | yes | yes |
| PostgreSQL V2 + migrations | yes | yes | yes |
| Dedicated Telegram collector identity | yes | yes | authorization/source access verified |
| PostgreSQL source lifecycle/catalog | yes | yes | 15 rows, 13 approved/readable |
| Raw Telegram persistence | yes | yes | **not yet observed on natural live message** |
| Cheap V2 prefilter | yes | yes | **not yet observed live** |
| Legacy-filter shadow telemetry | yes | yes | **not yet observed live** |
| Opportunity AI analysis | yes | yes with fakes | disabled, no live provider configured |
| Canonical Opportunities/dedup | yes | yes | not live-validated in this deployment |
| SearchProfiles/onboarding | yes | yes | owner bot UI works; AI onboarding not enabled |
| Matching | yes | yes | not live-validated end to end |
| Personalized delivery | yes | yes | owner-only boundary validated; no live lead delivery yet |
| Owner-only bot access | yes | yes/reviewed | owner positive path live-validated |
| Source discovery/audit | yes | yes | disabled in current deployment |
| Billing/payment abstractions | yes | yes | not production-configured |
| Persistent runtime/service | supporting code exists | n/a | **not authorized/deployed** |

## Credentials and incidents

No current secret value belongs in Git, docs, issue comments or chat transcripts.

Credentials that were exposed during setup/diagnostic work were rotated before
continuing. Historical credentials must be treated as invalid. Current
replacement values are not recorded in this repository.

## What is not complete

Do not describe the project as fully operational yet. The following gates remain:

1. natural live raw-message + shadow evidence;
2. AI provider/model/key selection with explicit cost limits;
3. bounded live Opportunity analysis;
4. owner SearchProfile/onboarding validation for the chosen AI route;
5. bounded matching + personalized delivery to the owner;
6. decision on any legacy-filter changes based on shadow evidence;
7. later discovery/audit rollout if still desired;
8. persistent runtime deployment only after bounded end-to-end evidence.

The authoritative order is in `docs/ACTIVE_PLAN.md`.
