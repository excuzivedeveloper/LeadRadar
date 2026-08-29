# LeadRadar — Active Plan

**Status:** CANONICAL / ACTIVE  
**Last verified:** 2026-08-29  
**Implementation baseline:** `f9884b196ed6a424ec69352597de66c1eeca331c`

This file defines execution order. A later capability being implemented in code
does not mean it may be enabled before earlier gates pass.

## Current position

Completed through:

```text
SERVER_PROMOTION_AND_OWNER_ALLOWLIST_CONFIGURATION
BOUNDED_FULL_RUNTIME_SAFETY_CANARY
SOURCE_ACTIVITY_AND_COLLECTOR_ROUTING_INVESTIGATION
CONTROLLED_COLLECTOR_MEMBERSHIP_PILOT
APPROVED_SOURCE_MEMBERSHIP_ROLLOUT_13_OF_13
CANONICAL_DOC_SYNC_FOR_LIVE_EVIDENCE_AND_MEMBERSHIP
```

The collector membership hypothesis is now experimentally confirmed:

```text
membership
-> natural Telegram NewMessage
-> raw_messages
-> cheap V2 prefilter
-> legacy-filter shadow telemetry
```

Current authorization state:

```text
SHADOW_LIVE_EVIDENCE=YES
COLLECTOR_MEMBERSHIP_READY=YES
READY_FOR_AI_SETUP=YES
PERSISTENT_RUNTIME_AUTHORIZED=NO
```

Current next execution stage:

```text
AI_PROVIDER_SETUP
```

## Step 0 — Pre-AI ingestion/shadow validation

**Status: COMPLETE.**

Evidence established:

- natural source traffic existed during the earlier 3600-second observation;
- zero raw ingestion was traced to the dedicated collector being a participant
  in 0/13 approved channels;
- filter strictness did not cause zero raw messages;
- after joining three approved sources, one natural live message produced one
  raw row, one cheap-prefilter row and one valid shadow row;
- shadow schema and exact filter SHA matched;
- no AI calls, Opportunities or deliveries occurred;
- the remaining approved sources were joined successfully;
- final dedicated collector membership is 13/13 approved public sources.

Membership is therefore a deployment prerequisite, not currently an evidenced
application-code defect.

## Step 1 — AI provider selection and configuration

**Status: NEXT EXECUTION STAGE.**

Goal: make one Opportunity-analysis provider route ready without making the
first live paid/model call in the same configuration step.

Required before any live provider call:

- inspect provider support in current implementation baseline;
- choose the exact provider deliberately;
- choose the exact model deliberately;
- verify current provider/model pricing from authoritative provider information;
- define low provider-side spend/rate limits where available;
- preserve repository daily/monthly budget guards;
- keep fallback disabled initially;
- enter the API key only through hidden server input;
- never print or commit the key;
- validate configuration without exposing the key;
- keep source discovery/audit/catch-up disabled;
- keep personalized delivery disabled;
- do not authorize persistent runtime.

Configuration readiness and the first live AI analysis call are separate gates.

Pass should produce:

```text
AI_PROVIDER_CONFIGURED=YES
AI_MODEL_CONFIGURED=YES
AI_SECRET_REPRINTED=NO
PROVIDER_LIVE_CALLS=0
READY_FOR_BOUNDED_AI_ANALYSIS=YES
PERSISTENT_RUNTIME_AUTHORIZED=NO
```

## Step 2 — Bounded live Opportunity analysis

**Blocked until Step 1 passes.**

Use a small bounded fresh-message observation with the now-correct 13/13
collector membership state.

Goals:

- prove `opportunity.analysis.v1` jobs are claimed correctly;
- make only explicitly bounded provider calls;
- confirm AI telemetry/provider/model/version fields;
- validate strict schema output;
- verify cache/dedup semantics;
- prove budget guards;
- materialize canonical Opportunities only from valid classifier output.

Do not enable personalized delivery in the same first AI canary.

## Step 3 — Owner SearchProfile/onboarding validation

Validate the owner-facing V2 SearchProfile path with the selected onboarding AI
route or an explicitly validated manual path.

Goals:

- owner-only bot gate remains enforced;
- draft profile creation;
- confirmation/activation;
- ownership isolation;
- active profile state suitable for matching.

Do not add additional users.

## Step 4 — Bounded matching and owner-only delivery

With valid live Opportunities and an active owner SearchProfile:

- run deterministic matching;
- inspect decision/trace evidence;
- confirm entitlement behavior;
- allow personalized delivery only to the single owner allowlist entry;
- verify delivery action callbacks;
- verify no retry storm and no non-owner send.

This is the first stage that should prove the intended user-facing lead-card flow
end to end.

## Step 5 — Evaluate accumulated legacy-filter shadow evidence

The legacy matcher is already live-observed in shadow, but one sample is not
enough to justify redesign.

Collect enough natural evidence before deciding whether to change:

- `min_score`;
- keyword weights;
- stop words;
- substring matching behavior.

Known candidate issue: substring stop-word matching can reject legitimate text.
Any change must be narrow, evidence-backed and independently reviewed. Do not
weaken the filter merely to manufacture output.

## Step 6 — Source discovery/audit rollout

**Later stage.**

Source discovery, Telegram graph/global/chat discovery and Source Audit exist in
code but remain disabled in deployment.

Enable them only as separate bounded tasks after core ingestion/AI/delivery
behavior is proven.

Do not combine discovery rollout with first AI setup or first delivery canary.

## Step 7 — Persistent runtime deployment

**Not currently authorized.**

Only after bounded end-to-end validations are clean should the project choose a
persistent process model.

Before authorizing persistence define:

- restart policy;
- log handling;
- session locking;
- graceful shutdown;
- health/observability;
- backup/rollback;
- Telegram membership provisioning/verification;
- rate/spend limits;
- shared-server resource boundaries.

A successful bounded `--run` does not authorize a daemon/systemd deployment.

## Explicit non-goals until ordered

Do not:

- enable catch-up to force test data;
- enable discovery concurrently with first AI setup;
- switch collector back to owner's main Telegram account;
- remove owner-only bot access;
- add automatic channel joining without a separately reviewed design;
- redesign legacy filter from one live shadow sample;
- modify unrelated shared-server services;
- treat implemented later-stage code as proof that live behavior has passed;
- start persistent runtime before the later persistence gate.
