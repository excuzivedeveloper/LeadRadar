# LeadRadar — Active Plan

**Status:** CANONICAL / ACTIVE  
**Last verified:** 2026-09-05
**Implementation baseline:** `a48b125bb486ad2b5f138840c8f8398a66f73088`

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
BOUNDED_ONE_SHOT_OPENROUTER_OPPORTUNITY_ANALYSIS
PR13_RU_EN_OWNER_CANARY_REPAIR
PR13_REPEAT_BOUNDED_OWNER_MVP_CANARY
BOUNDED_WEB_ONLY_OWNER_PROFILE_SOURCE_DISCOVERY
PR15_REVIEW_MERGE_AND_PRODUCTION_SYNC
PR15_ALEMBIC_20260904_0039
PR15_BOUNDED_RUNTIME_SHADOW_CANARY
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
LIVE_AI_ANALYSIS_VALIDATED=YES
READY_FOR_OPENROUTER_CONFIGURATION=COMPLETE
READY_FOR_BOUNDED_AI_ANALYSIS=COMPLETE

PR13_REVIEWED=YES
PR13_MERGED=YES
PR13_REPEAT_BOUNDED_CANARY=COMPLETED
MATCHING_PIPELINE=PASS
PR13_RU_EN_WEB_REPAIR_RESULT=INCONCLUSIVE_NO_RELEVANT_RU_EN_WEB_SAMPLE

PR14_IMPLEMENTED_IN_SHADOW=YES
PR14_EVIDENCE_RUNTIME_INSTRUMENTATION_IMPLEMENTED=YES
PR14_PRODUCTION_MATCH_POLICY_CHANGED=NO

PR15_MERGED=YES
PR15_PRODUCTION_SYNCED=YES
PR15_MIGRATION_APPLIED_PRODUCTION=YES
ALEMBIC_CURRENT=20260904_0039
ALEMBIC_HEADS=20260904_0039
SHADOW_RUNTIME_WIRED=YES
SHADOW_DURABLE_PERSISTENCE=YES
SHADOW_LIVE_VALIDATED=YES
PR15_BOUNDED_RUNTIME_SHADOW_CANARY=PASS
PRODUCTION_MATCH_POLICY_CHANGED=NO
DELIVERY_POLICY_CHANGED=NO

BOUNDED_WEB_ONLY_DISCOVERY_DURING_DEVELOPMENT=ALLOWED_AS_SEPARATE_TASK
PERSISTENT_SOURCE_DISCOVERY_AUTHORIZED=NO
TELEGRAM_DISCOVERY_AUTHORIZED=NO
SOURCE_AUDIT_AUTHORIZED=NO
AUTO_APPROVE_AUTHORIZED=NO
AUTO_JOIN_AUTHORIZED=NO

USEFUL_DELIVERY_PROVEN=NO
OWNER_DELIVERY_GATE=IN_PROGRESS_OR_NEXT
PERSISTENT_RUNTIME_AUTHORIZED=NO
READY_FOR_PERSISTENT_RUNTIME=NO
```

Current gate:

```text
BOUNDED_OWNER_DELIVERY_CANARY
```

Required execution sequence:

```text
1. complete the separately authorized bounded Owner Delivery Canary
2. prove runtime stopped and inspect body-free DB/delivery evidence
3. publish the exact final evidence report to a temporary GitHub evidence branch
4. ORCHESTRATOR reads the actual GitHub evidence before final verdict
5. if no relevant natural lead arrives, keep result INCONCLUSIVE; do not lower thresholds
6. run bounded WEB_ONLY candidate discovery separately as development maintenance when useful
7. keep Telegram discovery, Source Audit, auto-approve, auto-join and persistent discovery disabled
8. keep persistent runtime as a separate later gate
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
AI_JOB_PROCESSING_OCCURRED=NO
READY_FOR_BOUNDED_AI_ANALYSIS=YES
LIVE_AI_ANALYSIS_VALIDATED=NO
PERSISTENT_RUNTIME_AUTHORIZED=NO
```

## Step 2 — Bounded first live OpenRouter Opportunity analysis

**Status: COMPLETE.**

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

Observed result:

```text
OA_PIPELINE=PASS
OUTSTANDING_JOBS=0
RUNTIME_STOPPED=YES
```

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

**Status: PARTIAL.**

PR13 was reviewed, merged and repeat-canaried. A fresh natural C++/HFT lead
exercised the Opportunity Analysis and matching pipelines successfully, but it
did not provide a relevant RU/EN web sample. Therefore:

```text
PR13_REPEAT_BOUNDED_CANARY=COMPLETED
FRESH_NATURAL_LEAD=1
FRESH_SAMPLE=C++/HFT
MATCHING_PIPELINE=PASS
PR13_RU_EN_WEB_REPAIR_RESULT=INCONCLUSIVE_NO_RELEVANT_RU_EN_WEB_SAMPLE
USEFUL_DELIVERY_PROVEN=NO
READY_FOR_PERSISTENT_RUNTIME=NO
```

With valid live Opportunities and an active owner SearchProfile:

- run deterministic matching;
- inspect decision/trace evidence;
- confirm entitlement behavior;
- allow personalized delivery only to the single owner allowlist entry;
- verify delivery action callbacks;
- verify no retry storm and no non-owner send.

This stage still must prove the intended user-facing useful lead-card flow end
to end before persistent runtime is considered.

## Step 5 — Bounded runtime evidence-shadow canary

**Status: COMPLETE / PASS.**

PR15 is merged and production-synced at:

```text
PRODUCTION_HEAD=a48b125bb486ad2b5f138840c8f8398a66f73088
ALEMBIC_CURRENT=20260904_0039
ALEMBIC_HEADS=20260904_0039
```

The separately authorized bounded runtime shadow canary passed on fresh natural
traffic. Independent GitHub evidence established:

```text
FRESH_NATURAL_TRAFFIC_COUNT=2
RAW_MESSAGES_DELTA=2
OPPORTUNITIES_DELTA=1
MATCH_EVALUATION_RUNS_DELTA=1
MATCH_TRACES_DELTA=1
SHADOW_TRACE_DELTA=1
FRESH_CANARY_SHADOW_TRACE_COUNT=1
FRESH_CANARY_SHADOW_TIED_TO_LIVE_RAW=YES
FRESH_CANARY_SHADOW_INGESTION_ORIGIN=live
RAW_CONTENT_SHA256_VERIFIED=YES
RAW_MESSAGE_BODY_DUPLICATED_IN_SHADOW=NO
CURRENT_DECISION_PRESERVED=YES
SHADOW_DECISION_RECORDED=YES
SHADOW_LIVE_VALIDATED=YES
VERDICT=PASS
```

The current matcher remained authoritative; the validated sample was not
delivery-eligible, so this PR15 gate did not itself prove useful owner delivery.

The evidence report was independently read from temporary GitHub evidence branch
`evidence/pr15-shadow-canary-20260905`. Persistent runtime remains unauthorized.

## Step 6 — Evaluate accumulated legacy-filter and evidence-shadow data

The legacy matcher is already live-observed in shadow, but one sample is not
enough to justify redesign.

PR14 OpportunityAnalysisV2 evidence-aware matching shadow is wired for runtime
observation by PR15, but it still does not change production matching
thresholds, rank, delivery policy, provider configuration, discovery, catch-up
or persistent runtime.

Collect enough natural evidence before deciding whether to change:

- `min_score`;
- keyword weights;
- stop words;
- substring matching behavior.

Known candidate issue: substring stop-word matching can reject legitimate text.
Any change must be narrow, evidence-backed and independently reviewed. Do not
weaken the filter merely to manufacture output.

## Step 7 — Source discovery during development

**Status: BOUNDED WEB_ONLY CANDIDATE DISCOVERY ALLOWED; persistent discovery disabled.**

A separate bounded owner-profile discovery pass was already run on
2026-09-02 using local SearXNG in WEB_ONLY mode:

```text
RUN_KEY=owner-web-candidate-canary-20260902-v1
MODE=WEB_ONLY_CANDIDATE_ONLY
SOURCES_BEFORE=15
SOURCES_AFTER=20
CANDIDATES_BEFORE=2
CANDIDATES_AFTER=7
NEW_CANDIDATES=5
```

That run persisted candidate sources only. It did not approve or join them and
made no Telegram discovery calls.

During development, further **separately bounded WEB_ONLY** discovery tasks may
be used to grow the candidate pool without waiting for the entire Owner MVP to
finish. They must remain isolated from live delivery canaries.

Required development-mode boundaries:

```text
WEB_ONLY=YES
CANDIDATE_PERSISTENCE=YES
AUTO_APPROVE=NO
AUTO_JOIN=NO
COLLECTION_FROM_NEW_CANDIDATES=NO
SOURCE_AUDIT=NO
SOURCE_GRAPH_DISCOVERY=NO
TELEGRAM_GLOBAL_DISCOVERY=NO
TELEGRAM_CHAT_DISCOVERY=NO
PERSISTENT_SOURCE_DISCOVERY=NO
```

Full-runtime discovery flags remain disabled. Promotion of candidates to approved
sources, Telegram membership/joining, Source Audit, Telegram graph/global/chat
discovery, and persistent discovery each remain separate reviewed/authorized
gates.

Do not combine a bounded discovery pass with a delivery, AI, or matching canary.

## Step 8 — Persistent runtime deployment

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
