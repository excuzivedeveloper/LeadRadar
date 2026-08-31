# LeadRadar — Active Plan

**Status:** CANONICAL / ACTIVE  
**Last verified:** 2026-08-31
**Implementation baseline:** `d92b0446be19f391bb8f479387b27d914c081e35`

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
OPENROUTER_FIRST_CLASS_OPPORTUNITY_IMPLEMENTATION
OPENROUTER_IMPLEMENTATION_SERVER_SYNC
OPENROUTER_MINIMAX_CONFIGURATION_ONLY
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

Current next execution stage:

```text
BOUNDED_ONE_SHOT_OPENROUTER_OPPORTUNITY_ANALYSIS
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

## Step 1 — OpenRouter + MiniMax configuration-only

**Status: COMPLETE.**

Goal: make the selected Opportunity Analysis route ready without making the
first live provider/model call in the same configuration step.

Selected initial route:

```text
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPPORTUNITY_ANALYSIS_PROVIDER=openrouter
OPPORTUNITY_ANALYSIS_MODEL=minimax/minimax-m3:free
OPPORTUNITY_ANALYSIS_TEMPERATURE=0
OPPORTUNITY_ANALYSIS_MAX_OUTPUT_ATTEMPTS=1
OPPORTUNITY_ANALYSIS_FALLBACK_ENABLED=false
```

This is the chosen route for the first bounded Opportunity Analysis validation,
not a permanent provider lock-in.

Required before any live provider call:

- reverify current `minimax/minimax-m3:free` availability and pricing from
  authoritative provider information;
- define low provider-side spend/rate limits where available;
- preserve repository daily/monthly budget guards;
- keep fallback disabled;
- enter the API key only through hidden server input;
- never print or commit the key;
- validate configuration without exposing the key;
- keep source discovery/audit/catch-up disabled;
- keep personalized delivery disabled;
- do not authorize persistent runtime.

Configuration readiness and the first live AI analysis call are separate gates.
Do not start full `python -m freelancer_bot --run` after inserting the key in
this configuration-only task.

Reason: the current implementation has no separate
`OPPORTUNITY_ANALYSIS_ENABLED` switch. Once the matching Opportunity Analysis
key is configured, full `--run` can construct the analyzer, activate the
`opportunity.analysis.v1` handler, claim existing pending jobs and make provider
calls. `AI_REPLY_ENABLED=false` controls reply drafting only and does not
disable Opportunity Analysis.

Pass should produce:

```text
OPENROUTER_API_KEY_CONFIGURED=YES
OPPORTUNITY_ANALYSIS_PROVIDER=openrouter
OPPORTUNITY_ANALYSIS_MODEL=minimax/minimax-m3:free
AI_SECRET_REPRINTED=NO
PROVIDER_LIVE_CALLS=0
AI_JOB_PROCESSING_OCCURRED=NO
READY_FOR_BOUNDED_AI_ANALYSIS=YES
LIVE_AI_ANALYSIS_VALIDATED=NO
PERSISTENT_RUNTIME_AUTHORIZED=NO
```

## Step 2 — Bounded first live OpenRouter Opportunity analysis

**Status: NEXT EXECUTION STAGE after the one-shot command implementation is
merged and server-synced.**

Use one narrowly bounded Opportunity Analysis validation with OpenRouter and
`minimax/minimax-m3:free`.

Required operator mechanism:

```bash
python -m freelancer_bot --opportunity-analysis-job-id <UUID>
```

The UUID must be an explicit `opportunity.analysis.v1` durable job selected from
fresh preflight evidence. Do not choose an arbitrary queued job automatically.
With `OPPORTUNITY_ANALYSIS_MAX_OUTPUT_ATTEMPTS=1` and
`OPPORTUNITY_ANALYSIS_FALLBACK_ENABLED=false`, one invocation is bounded to at
most one provider request and exits after one selected-job processing attempt.

Goals:

- prove `opportunity.analysis.v1` jobs are claimed correctly;
- make only explicitly bounded provider calls;
- confirm telemetry includes `provider=openrouter`;
- confirm requested model is `minimax/minimax-m3:free`;
- validate strict schema output;
- validate grounding;
- verify cache/dedup semantics;
- prove budget guards;
- materialize canonical Opportunities only from valid classifier output.

Do not enable personalized delivery, discovery, catch-up or persistent runtime
in the same first AI canary.

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
- run full `--run` for the first live Opportunity Analysis canary;
- switch collector back to owner's main Telegram account;
- remove owner-only bot access;
- add automatic channel joining without a separately reviewed design;
- redesign legacy filter from one live shadow sample;
- modify unrelated shared-server services;
- treat implemented later-stage code as proof that live behavior has passed;
- start persistent runtime before the later persistence gate.
