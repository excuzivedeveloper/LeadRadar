# LeadRadar — Active Plan

**Status:** CANONICAL / ACTIVE  
**Last verified:** 2026-08-27  
**Implementation baseline:** `f9884b196ed6a424ec69352597de66c1eeca331c`

This file defines the execution order. A later capability being implemented in
code does not mean it may be enabled before earlier gates pass.

## Current position

Completed through:

```text
SERVER_PROMOTION_AND_OWNER_ALLOWLIST_CONFIGURATION
FIRST_600S_FULL_RUNTIME_CANARY
```

The first full-runtime canary was safe but inconclusive because no natural
Telegram messages arrived.

Current next stage:

```text
FOLLOWUP_BOUNDED_SHADOW_EVIDENCE
```

Current authorization state:

```text
READY_FOR_AI_SETUP=NO
PERSISTENT_RUNTIME_AUTHORIZED=NO
```

## Step 0 — Documentation synchronization

**Status:** current docs workstream.

Goal: make repository documentation self-contained for a new engineer/AI.

This step changes documentation only. It must not alter runtime behavior,
credentials or server state.

After this docs-only workstream is merged, continue with Step 1.

## Step 1 — Follow-up bounded live shadow evidence

**Status:** NEXT EXECUTION STAGE.

Run full `--run` in a bounded foreground window using only natural new source
traffic.

Current planned constraints:

```text
max observation = 3600 seconds
early success target = 3 new raw + 3 new shadow rows
catch-up = off
AI = off
discovery = off
legacy delivery = off
persistent service = no
```

A read-only latest-message metadata diagnostic may be used before the run to
understand whether the 13 approved sources are currently active. Message bodies
must not be printed or ingested by that diagnostic.

Pass requires at least one natural new raw message and corresponding valid
shadow evidence at the observation cap (3 is preferred for early stop):

```text
schema_version=legacy-filter-shadow.v1
filter SHA=current config/filters.json SHA
min_score=current filter min_score
AI calls=0
new Opportunities=0
new deliveries=0
```

If no natural message arrives after the extended window, stop and return to the
orchestrator. Do not turn on catch-up merely to manufacture evidence.

## Step 2 — AI provider selection and configuration

**Blocked until Step 1 passes.**

Choose the provider/model deliberately rather than accepting repository defaults
as a production decision.

Required before any live provider call:

- verify provider is supported by current config;
- choose exact model;
- set operator-verified pricing inputs where required;
- set low provider-side spend/rate limits;
- preserve repository daily/monthly budget guards;
- keep fallback disabled initially;
- enter API key only through hidden server input;
- never print the key;
- keep discovery disabled.

Provider configuration readiness should be separated from the first real AI
analysis call.

## Step 3 — Bounded live Opportunity analysis

**Blocked until Step 2 is configured.**

Use a small bounded fresh-message window.

Goals:

- prove `opportunity.analysis.v1` jobs are claimed correctly;
- confirm AI telemetry/provider/model/version fields;
- validate strict schema output;
- verify cache/dedup semantics;
- prove budget guards;
- materialize canonical Opportunities only from valid classifier output.

Do not automatically enable personalized delivery in the same first AI canary.

## Step 4 — Owner SearchProfile/onboarding validation

Validate the owner-facing V2 SearchProfile path with the chosen onboarding AI
route (or explicitly validated manual path).

Goals:

- owner-only bot gate still enforced;
- draft profile creation;
- confirmation/activation;
- ownership isolation;
- active profile state suitable for matching.

Do not add additional users yet.

## Step 5 — Bounded matching and owner-only delivery

With valid live Opportunities and an active owner SearchProfile:

- run matching;
- inspect deterministic decision/trace evidence;
- confirm entitlement behavior;
- allow personalized delivery only to the single owner allowlist entry;
- verify delivery action callbacks;
- verify no retry storm and no non-owner send.

This is the first stage that should prove the intended user-facing lead card
flow end to end.

## Step 6 — Evaluate legacy-filter shadow evidence

Only after enough real shadow evidence exists, decide whether the preserved
legacy matcher should change.

Known candidate issue:

- substring stop-word matching can cause false positives inside legitimate
  words.

Do not rewrite the accumulated anti-spam/anti-noise rules wholesale. Any change
must be narrow, evidence-backed and independently reviewed.

## Step 7 — Source discovery/audit rollout

**Later stage.**

Source discovery, Telegram graph/global/chat discovery and Source Audit already
exist in code but remain disabled in the current deployment.

Enable them only as separate bounded tasks after core ingestion/AI/delivery
behavior is proven.

Do not combine discovery rollout with the first AI or delivery canary.

## Step 8 — Persistent runtime deployment

**Not currently authorized.**

Only after bounded end-to-end validations are clean should the project choose a
persistent process model (for example systemd or another explicit deployment
mechanism).

Before authorizing persistence, define:

- restart policy;
- log handling;
- session locking;
- graceful shutdown;
- health/observability;
- backup/rollback;
- rate/spend limits;
- shared-server resource boundaries.

A successful bounded `--run` does not itself authorize a persistent service.

## Explicit non-goals until ordered

Do not:

- enable catch-up to force test data;
- enable AI before live shadow evidence;
- enable discovery concurrently with first AI setup;
- switch the collector back to the owner's main Telegram account;
- remove owner-only bot access;
- redesign the legacy filter without evidence;
- modify unrelated shared-server services;
- treat existing later-stage code as proof that live behavior has passed.
