# LeadRadar — Current State

**Status:** CANONICAL  
**Snapshot date:** 2026-09-05
**Implementation baseline:** `a48b125bb486ad2b5f138840c8f8398a66f73088`
**Current deployed repository head:** `a48b125bb486ad2b5f138840c8f8398a66f73088`

## Executive status

LeadRadar has completed the pre-AI live ingestion/shadow gate, OpenRouter
configuration and bounded Opportunity Analysis validation, PR13 matching repair,
and the PR15 production shadow-instrumentation rollout plus live shadow canary.

PR15 is now merged, production-synced and live-validated. The current product
gate is useful owner-only delivery from a relevant fresh natural Opportunity.
A separately bounded Owner Delivery Canary is the active/next gate; its final
verdict must not be inferred until its runtime and DB evidence are complete.

Bounded WEB_ONLY candidate-source discovery is permitted as a separate
development-maintenance task. Persistent discovery, Telegram discovery, Source
Audit, auto-approval and auto-joining remain disabled.

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
LIVE_AI_ANALYSIS_VALIDATED=YES

PR13_REVIEWED=YES
PR13_MERGED=YES
PR13_REPEAT_BOUNDED_CANARY=COMPLETED
MATCHING_PIPELINE=PASS

PR15_MERGED=YES
PR15_PRODUCTION_SYNCED=YES
PR15_MIGRATION_APPLIED_PRODUCTION=YES
PR15_SHADOW_LIVE_VALIDATED=YES
PR15_BOUNDED_RUNTIME_SHADOW_CANARY=PASS
ALEMBIC_CURRENT=20260904_0039
ALEMBIC_HEADS=20260904_0039
PRODUCTION_MATCH_POLICY_CHANGED=NO
DELIVERY_POLICY_CHANGED=NO

BOUNDED_WEB_ONLY_DISCOVERY_DURING_DEVELOPMENT=ALLOWED_AS_SEPARATE_TASK
PERSISTENT_SOURCE_DISCOVERY_AUTHORIZED=NO
TELEGRAM_DISCOVERY_AUTHORIZED=NO
SOURCE_AUDIT_AUTHORIZED=NO
AUTO_APPROVE_AUTHORIZED=NO
AUTO_JOIN_AUTHORIZED=NO

OWNER_DELIVERY_CANARY=COMPLETED
OWNER_DELIVERY_CANARY_VERDICT=INCONCLUSIVE_NO_FRESH_RELEVANT_OWNER_DELIVERY
OWNER_ONLY_DELIVERY_SAFETY=PASS
REAL_OWNER_DELIVERY_PROVEN=NO
USEFUL_DELIVERY_PROVEN=NO
OA_OPENROUTER_RELIABILITY_FINDING=YES
OA_OPENROUTER_RELIABILITY_REVIEW=COMPLETE
OA_OPENROUTER_RELIABILITY_VERDICT=E_MIXED
OA_CODE_FIX_REQUIRED=YES
PR17_OPEN=YES
PR17_HEAD=85a33864c50cd690e1b2f4fc967b6365ffeba937
PR17_FIRST_REVIEW=CHANGES_REQUESTED
PR17_FIRST_REVIEW_FINDING_COUNT=1
PR17_FIRST_REVIEW_FINDING_SEVERITY=MEDIUM
PR17_NARROW_REREVIEW=APPROVE
PR17_PREVIOUS_MEDIUM_RESOLVED=YES
PR17_READY_FOR_OWNER_MERGE_AUTHORIZATION=YES
OA_PROVIDER_ROUTE_SWITCH_AUTHORIZED=NO
PERSISTENT_RUNTIME_AUTHORIZED=NO
READY_FOR_PERSISTENT_RUNTIME=NO
```

The exact next execution sequence is:

```text
obtain Owner merge authorization for PR #17 exact head 85a33864c50cd690e1b2f4fc967b6365ffeba937
-> merge only if exact PR head/state still match
-> keep production runtime stopped
-> sync production checkout to resulting main merge head
-> apply Alembic 20260905_0040
-> verify Alembic current=head and production worktree clean
-> then separately authorize a new bounded Owner Delivery Canary
-> persistent runtime remains a separate later gate
```

Migration `20260904_0039` is applied and PR15 live shadow validation has passed.
The current production matcher and delivery policy remain unchanged.

Full-runtime discovery, catch-up, legacy delivery and persistent runtime remain
disabled. Separately bounded WEB_ONLY candidate discovery is allowed during
development. A useful real owner delivery is not yet proven at this snapshot.

## Repository and migration state

Production implementation baseline:

```text
a48b125bb486ad2b5f138840c8f8398a66f73088
```

Current server repository head:

```text
a48b125bb486ad2b5f138840c8f8398a66f73088
```

Runtime/tooling baseline:

```text
Python=3.14.7
uv=0.12.2
PostgreSQL=18.x
Production Alembic current=20260904_0039
Repository Alembic head=20260904_0039
```

The current migration set includes:

```text
message_prefilter_shadow_evaluations
schema=legacy-filter-shadow.v1
opportunity_evidence_shadow_traces
schema=opportunity_evidence_shadow_trace.v1
```

Relevant merged adaptation milestones:

- PR #1 — Codence profile/filter adaptation while preserving upstream
  anti-noise behavior.
- PR #2 — V2 prefilter legacy-filter shadow telemetry.
- PR #3 — owner-only Telegram bot allowlist with private-chat enforcement and
  outbound delivery defense in depth.
- PR #4 — canonical self-contained documentation for new agents.
- PR #6 — first-class OpenRouter Opportunity Analysis provider support.
- PR #13 — RU/EN owner-canary matching repair, reviewed and merged.

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
ROWS=20
APPROVED=13
CANDIDATE=7
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

### Bounded WEB_ONLY source discovery

A bounded owner-profile WEB_ONLY discovery pass was completed on 2026-09-02:

```text
RUN_KEY=owner-web-candidate-canary-20260902-v1
MODE=WEB_ONLY_CANDIDATE_ONLY
SOURCES_BEFORE=15
SOURCES_AFTER=20
CANDIDATES_BEFORE=2
CANDIDATES_AFTER=7
NEW_CANDIDATES=5
```

Five new candidates were persisted from web-search evidence. The run made no
Telegram discovery calls and did not auto-approve, auto-join, audit, or collect
from those candidates.

This bounded WEB_ONLY mode may be repeated as a separate development task to
grow the candidate pool. It does **not** authorize persistent discovery or any
promotion/join automation.

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
TELEGRAM_GLOBAL_DISCOVERY_ENABLED=false
TELEGRAM_CHAT_DISCOVERY_ENABLED=false

AI_REPLY_ENABLED=false

OPENAI_API_KEY_CONFIGURED=NO
DEEPSEEK_API_KEY_CONFIGURED=NO
TOKENROUTER_API_KEY_CONFIGURED=NO
OPENROUTER_API_KEY_CONFIGURED=YES
```

There is no persistent LeadRadar app/bot/collector process.

These full-runtime flags intentionally remain false even though separately
bounded WEB_ONLY candidate discovery runs are allowed during development.
Those runs are explicit one-shot maintenance tasks, not persistent discovery.


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
LIVE_AI_ANALYSIS_VALIDATED=YES
READY_FOR_OPENROUTER_CONFIGURATION=COMPLETE
READY_FOR_BOUNDED_AI_ANALYSIS=COMPLETE
```

Important runtime invariant: the current implementation has no separate
`OPPORTUNITY_ANALYSIS_ENABLED` switch. Once the matching Opportunity Analysis
provider key is configured, starting full `python -m freelancer_bot --run` can
construct the analyzer, activate the `opportunity.analysis.v1` handler, claim
existing pending analysis jobs and make provider calls. `AI_REPLY_ENABLED=false`
does not disable Opportunity Analysis; it gates reply drafting only.

The production-safe operator entrypoint for the first bounded AI canary is:

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

### PR13 repeat bounded Owner MVP canary

PR13 was reviewed, merged and server-synced to production head
`eddc972a111f75ac2c634a3a56aba61672060d36`. The repeat bounded canary is
complete and the runtime is stopped.

Observed:

```text
OUTSTANDING_JOBS=0
FRESH_NATURAL_LEAD=1
FRESH_SAMPLE=C++/HFT
OA_PIPELINE=PASS
MATCHING_PIPELINE=PASS
PR13_RU_EN_WEB_REPAIR_RESULT=INCONCLUSIVE_NO_RELEVANT_RU_EN_WEB_SAMPLE
USEFUL_DELIVERY_PROVEN=NO
READY_FOR_PERSISTENT_RUNTIME=NO
```

The PR13 RU/EN web repair was not invalidated; the canary did not contain a
relevant fresh RU/EN web sample.

### PR15 bounded runtime shadow canary

PR15 was merged and production-synced to
`a48b125bb486ad2b5f138840c8f8398a66f73088`; migration
`20260904_0039` is current and head.

The bounded live shadow canary passed:

```text
FRESH_NATURAL_TRAFFIC_COUNT=2
RAW_MESSAGES_DELTA=2
OPPORTUNITIES_DELTA=1
MATCH_EVALUATION_RUNS_DELTA=1
MATCH_TRACES_DELTA=1
SHADOW_TRACE_DELTA=1
FRESH_CANARY_SHADOW_TRACE_COUNT=1
FRESH_CANARY_SHADOW_TIED_TO_LIVE_RAW=YES
RAW_CONTENT_SHA256_VERIFIED=YES
RAW_MESSAGE_BODY_DUPLICATED_IN_SHADOW=NO
CURRENT_DECISION_PRESERVED=YES
SHADOW_DECISION_RECORDED=YES
SHADOW_LIVE_VALIDATED=YES
VERDICT=PASS
```

The exact evidence report was independently read from temporary GitHub branch
`evidence/pr15-shadow-canary-20260905`; persistent runtime was not authorized.

### Owner Delivery Canary

The separately authorized 3600-second Owner Delivery Canary completed on
2026-09-05. The final actual report was independently read from temporary GitHub
evidence branch `evidence/owner-delivery-canary-20260905`.

Verified result:

```text
FRESH_LIVE_RAW_COUNT=4
FRESH_LIVE_OPPORTUNITY_COUNT=2
FRESH_LIVE_MATCH_TRACE_COUNT=2
FRESH_LIVE_ELIGIBLE_MATCH_COUNT=0

NEW_PERSONALIZED_DELIVERY_COUNT=0
NEW_NON_OWNER_DELIVERY_COUNT=0
FRESH_OWNER_SENT_DELIVERY_COUNT=0

OWNER_ONLY_DELIVERY_SAFETY=PASS
REAL_OWNER_DELIVERY_PROVEN=NO

RUNNING_DURABLE_JOB_COUNT_AFTER_CANARY=0
QUEUED_DURABLE_JOB_COUNT_AFTER_CANARY=0

VERDICT=INCONCLUSIVE_NO_FRESH_RELEVANT_OWNER_DELIVERY
```

Evidence commit:

```text
273ec1fb83b3726b8c086f6bd80fc8487ebcb530
```

Report SHA-256:

```text
3997b167b7a96f1718343f623406f7332a3af47e7642a81e42838b7e64caa7c8
```

The result is inconclusive rather than failed because no fresh Opportunity was
eligible under the unchanged production matcher. No delivery was scheduled or
sent, and no non-owner delivery occurred.

During the same bounded runtime, separate server evidence showed an OA/OpenRouter
reliability issue: two `opportunity.analysis.v1` jobs completed and two failed
with `OpportunityAnalysisOutputError`; observed failures included invalid or
ungrounded model output, and one retry encountered provider HTTP 429. This
finding is tracked separately from the formal delivery-canary verdict.

### OA / OpenRouter reliability diagnosis

A narrow read-only/offline review after the Owner Delivery Canary completed with:

```text
VERDICT=E — MIXED
SEVERITY=MEDIUM
CURRENT_MAX_PROVIDER_CALLS_PER_OA_JOB=3
FAIL_CLOSED=YES
DOWNSTREAM_MATCHING_SAFETY=PASS
```

Confirmed issues:

- `OpportunityAnalysisOutputError` inherits retryability, so exhausted output
  validation/grounding failures can consume generic durable retries;
- the OA enqueue path relies on the generic durable default
  `max_attempts=3`;
- HTTP 429 is retryable but generic worker pacing is flat and does not honor
  provider `Retry-After`;
- the current OpenRouter path uses `json_object` plus schema-in-prompt rather
  than native strict `json_schema`;
- persisted telemetry collapses rate-limit, transport, schema and grounding
  failures too aggressively.

Grounding correctly failed closed and must remain strict. No immediate provider
or model switch is authorized from this evidence alone.

The next engineering gate is a narrow offline code/retry-policy fix followed by
independent review. No production change is authorized by the diagnosis itself.

### PR #17 first review result

PR #17 first narrow review on
`18943124732166fb51807cd4d8ff531c6542504b` returned:

```text
FINAL_VERDICT=CHANGES_REQUESTED
FINDING_COUNT=1
FINDING_SEVERITY=MEDIUM
GENERIC_WORKER_RETRY_HINT_SAFETY=FINDING
```

The OA-specific retry envelope, terminal output-failure behavior, 429 handling,
telemetry taxonomy, durable-attempt correlation, ContextVar isolation and
migration `20260905_0040` all passed review.

The only required correction is defensive normalization of generic
`retry_after_seconds` at `DurableWorker`: invalid/negative/non-finite values
must fall back safely, valid hints must be capped, and malformed hints must not
break terminal/non-retryable failure recording. A generic non-OA regression test
is required.

### PR #17 narrow re-review approval

PR #17 follow-up head:

```text
85a33864c50cd690e1b2f4fc967b6365ffeba937
```

Narrow re-review of the only previous MEDIUM concluded:

```text
PREVIOUS_MEDIUM_RESOLVED=YES
GENERIC_WORKER_RETRY_HINT_SAFETY=PASS
WORKER_RETRY_HINT_GENERIC_CAP_SECONDS=3600.0
OA_BEHAVIOR_CHANGED=NO
MIGRATION_CHANGED=NO
FINAL_VERDICT=APPROVE
```

The follow-up consists of one commit and only two files:
`freelancer_bot/worker.py` and `tests/test_worker.py`. CI is green on the
exact approved head. PR #17 is review-complete and awaiting explicit Owner merge
authorization.

## Implemented vs currently live-validated

| Capability | Implemented | Current deployment/live evidence |
| --- | --- | --- |
| Safe CLI/config | yes | validated |
| PostgreSQL V2 + migrations | yes | validated |
| Dedicated collector identity | yes | validated |
| PostgreSQL source lifecycle/catalog | yes | 20 rows; 13 approved; 7 candidates after bounded WEB_ONLY discovery |
| Collector membership prerequisite | deployment state | validated; 13/13 joined |
| Raw Telegram persistence | yes | **live-validated** |
| Cheap V2 prefilter | yes | **live-validated** |
| Legacy-filter shadow telemetry | yes | **live-validated** |
| OpenRouter Opportunity provider | yes | offline tests and server sync passed; runtime configured |
| OpenRouter runtime configuration | n/a | configured; bounded Opportunity Analysis canary completed |
| Opportunity AI analysis | yes | bounded live path passed for one fresh natural lead sample |
| OpportunityAnalysisV2 evidence-aware matching shadow | yes; deterministic explicit-evidence contract and SearchProfile-derived capability/platform surface | **live-validated via PR15 bounded runtime canary**; separate durable persistence; `SHADOW_LIVE_VALIDATED=YES`, `PRODUCTION_MATCH_POLICY_CHANGED=NO`, `DELIVERY_POLICY_CHANGED=NO` |
| Canonical Opportunities/dedup | yes | not live-validated with real AI output |
| SearchProfiles/onboarding | yes | owner UI exists; AI onboarding not enabled |
| Matching | yes; includes local high-precision RU/EN technical concept bridge | PR13 reviewed/merged; repeat bounded canary completed with C++/HFT sample; RU/EN web repair result inconclusive because no relevant fresh RU/EN web sample appeared |
| Personalized delivery | yes | bounded Owner Delivery Canary completed INCONCLUSIVE; owner-only safety passed; no eligible fresh match and no real sent delivery yet |
| Owner-only bot access | yes | owner positive path live-validated |
| Source discovery/audit | yes | bounded WEB_ONLY candidate discovery live-used (15→20 sources; candidates 2→7); persistent/Telegram discovery and Source Audit remain disabled |
| Persistent runtime/service | supporting code exists | **not authorized/deployed** |

## Credentials and incidents

No current secret value belongs in Git, docs, issue comments or chat transcripts.
Credentials exposed during earlier setup/diagnostic work were rotated before
continuing. Historical values are invalid and must not be reused.

## What remains

The ingestion/shadow, bounded OpenRouter Opportunity Analysis, PR13 matching,
PR15 production shadow instrumentation, and PR15 live shadow validation gates
are complete.

Remaining ordered work:

1. implement the narrow OA/OpenRouter reliability remediation offline;
2. independently review the resulting PR before any merge or production action;
3. after reviewed production sync, repeat the bounded Owner Delivery Canary to
   prove a real fresh owner-only sent delivery;
4. continue separate bounded WEB_ONLY candidate discovery during development
   when useful, without auto-approval, joining, Source Audit or Telegram
   discovery;
5. evaluate accumulated matching/shadow evidence before any threshold or policy
   changes;
6. evaluate provider/model strict-schema capability later as a separate gate,
   not as part of the immediate fix;
7. separately review candidate promotion/joining and broader discovery/audit
   rollout;
8. authorize persistent runtime only after bounded end-to-end Owner MVP
   validation and operational safeguards are complete.

The authoritative order is in `docs/ACTIVE_PLAN.md`.
