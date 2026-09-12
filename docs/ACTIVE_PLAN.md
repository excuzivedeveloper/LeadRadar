# LeadRadar — Active Plan

**Status:** CANONICAL / ACTIVE  
**Last verified:** 2026-09-12
**Implementation baseline:** `81a675b72ed4c1229cedad28e5d2e1f56bac1f66`
**Latest verified production evidence head:** `b660bdd633137f13dae5a8524f14d36c0f5ecd05`

This file defines execution order. Implemented capability does not imply authorization to activate it.

## Current production baseline

```text
LATEST_VERIFIED_PRODUCTION_EVIDENCE_HEAD=b660bdd633137f13dae5a8524f14d36c0f5ecd05
IMPLEMENTATION_BASELINE=81a675b72ed4c1229cedad28e5d2e1f56bac1f66
BRANCH=main
TRACKED_WORKTREE=CLEAN
ALEMBIC_CURRENT=20260908_0042
PERSISTENT_RUNTIME=STOPPED
PROFILE_DISCOVERY_INTENT_VERSION=profile-discovery-intent.v2
```

Verified service state remains:

```text
POSTGRES=running healthy on 127.0.0.1:55432
SEARXNG=running on 127.0.0.1:8888
VAULTWARDEN=running healthy on 127.0.0.1:8080 and NO-TOUCH
```

Verified safety state remains:

```text
SOURCE_DISCOVERY_ENABLED=false
SOURCE_AUDIT_ENABLED=false
TELEGRAM_GLOBAL_DISCOVERY_ENABLED=false
SOURCE_GRAPH_DISCOVERY_ENABLED=false
AI_REPLY_ENABLED=false
PERSISTENT_RUNTIME_AUTHORIZED=NO
```

## Completed current chain

```text
PR23_MERGED=YES
PR23_PRODUCTION_SYNCED=YES
PR23_SEARXNG_RECOVERY=PASS
PR23_BOUNDED_WEB_CANARY=PASS

PR24_MERGED=YES
PR24_PRODUCTION_SYNC=PASS
PR24_POST_SYNC_VERIFICATION=PASS
PR24_FULL_BOUNDED_STAGE_A_OFFLINE=PASS

PR25_REVIEWED=PASS
PR25_MERGED=YES
PR25_PRODUCTION_DOCS_SYNC=CARRIED_BY_PR27

PR27_REVIEWED=PASS
PR27_MERGED=YES
PR27_PRODUCTION_SYNC=PASS
PR27_POST_SYNC_VERIFICATION=PASS
PR27_TECHNICAL_PRELIVE=PASS
PR27_BOUNDED_WEB_CANARY=PASS
PR27_V2_INTENT_PERSISTENCE=PASS
PR27_ANGLE_ATTRIBUTION_READBACK=PASS

CURRENT_SESSION_TELEGRAM_IDENTITY_GATE=PASS
CURRENT_TELETHON_SESSION_COLLECTOR_ACCOUNT_ID=2
SOURCE_19_20_BOUNDED_TELEGRAM_ACCESS_FRESHNESS_PROBE=PASS

PR29_REVIEWED=PASS
PR29_MERGED=YES
PR29_PRODUCTION_DOCS_SYNC=PASS
COLLECTOR_1_CONTROLLED_CLEANUP=PASS
ACTIVE_TELEGRAM_COLLECTOR_IDS=2

PR30_REVIEWED=PASS
PR30_MERGED=YES
PR30_PRODUCTION_DOCS_SYNC=PASS
SOURCE_19_20_EXISTING_NOTIFICATION_ROWS_DIAGNOSTIC=PASS
SOURCE_19_OWNER_CANDIDATE_NOTIFICATION=sent
SOURCE_20_OWNER_CANDIDATE_NOTIFICATION=sent
```

The bounded planner contract remained:

```text
GENERATED=36
EXACT_DUPLICATES=0
NEAR_DUPLICATES=2
EXECUTABLE=34
SELECTED=12
SELECTED_DIRECT=4
SELECTED_BUYER_HABITAT=4
SELECTED_ADJACENT=4
```

## PR23 comparison baseline

```text
RUN_KEY=owner-profile-web-pr23-bounded-20260910-v1
DISCOVERY_RUN_ID=50de44e5-1b17-4f08-9a12-86b6d899f4ab
SEARCH_RESULTS_CONSIDERED=7
TELEGRAM_LIKE_RESULTS=6
UNIQUE_CANDIDATES=4
KNOWN_CANDIDATES=4
NEW_CANDIDATES=0
USEFUL_YIELD_ANGLE=direct_only
```

This baseline remains historical comparison evidence.

## Historical PR24 live attempts

The first PR24 canary authorization was consumed by an invocation using the wrong CLI namespace. Parsing rejected the command before Web execution. A later correctly namespaced authorized invocation failed before `discovery_runs` creation because the immutable `profile-discovery-intent.v1` identity conflicted with changed `generated_web_queries`. A second invocation was accidentally issued without authorization.

```text
RETIRED_RUN_KEY=owner-profile-web-pr24-bounded-20260911-v1
RETIRED_RUN_KEY_STATUS=RETIRED_DO_NOT_REUSE
AUTHORIZED_LIVE_COMMAND_ATTEMPTS=1
LIVE_COMMAND_ATTEMPTS=2
SECOND_WEB_ATTEMPT_AUTHORIZED=NO
```

These failed PR24 attempts remain historical evidence; they are not evidence that PR27 live Web execution failed.

## PR27 Web canary — completed

PR27 repaired the immutable intent contract by introducing `profile-discovery-intent.v2`. The earlier technical PRELIVE correctly observed `PERSISTED_V2_COUNT=0`; that was a read-only pre-live fact. The later authorized live canary persisted the v2 row and completed:

```text
PRODUCTION_HEAD=f39eb215526c9ff18bd2227ccf0f3cd40304407f
RUN_KEY=owner-profile-web-pr27-bounded-20260911-v1
DISCOVERY_RUN_ID=6a529712-6a7f-44a4-bd39-c8b23d25d44b
LIVE_COMMAND_EXIT_CODE=0
DISCOVERY_RUN_STATUS=completed
GENERATED_QUERY_COUNT=36
EXECUTABLE_QUERY_COUNT=34
SELECTED_QUERY_COUNT=12
EXECUTED_QUERY_COUNT=12
SEARCH_RESULTS_CONSIDERED=19
TELEGRAM_LIKE_CANDIDATES=18
UNIQUE_CANDIDATES=4
KNOWN_CANDIDATES=4
NEW_CANDIDATES=0
DISCOVERY_RUN_RESULT_COUNT=4
DISCOVERY_RUN_MATERIALIZED_COUNT=4
CREATED_RESULT_COUNT=0
EXISTING_RESULT_COUNT=4
PERSISTED_V2_COUNT=1
PERSISTED_V2_INTENT_ID=b3f53d57-afd9-55e1-b822-77d687fe466d
CURRENT_V2_ID_MATCH=YES
CURRENT_V2_CONTENT_MATCH=YES
CURRENT_V2_CONFLICT_PRESENT=NO
SEARXNG_EFFECTIVE_STATE=READY
FLOOD_OR_BACKEND_FAILURE=NONE
AUTHORIZATION_CONSUMED=YES
RETRY_ALLOWED=NO
```

PR23 -> PR27 bounded comparison:

```text
PR23_SEARCH_RESULTS=7
PR27_SEARCH_RESULTS=19
DELTA_SEARCH_RESULTS=12
PR23_TELEGRAM_LIKE=6
PR27_TELEGRAM_LIKE=18
DELTA_TELEGRAM_LIKE=12
PR23_UNIQUE_CANDIDATES=4
PR27_UNIQUE_CANDIDATES=4
DELTA_UNIQUE_CANDIDATES=0
PR23_NEW_CANDIDATES=0
PR27_NEW_CANDIDATES=0
DELTA_NEW_CANDIDATES=0
```

## Angle attribution — proven scope

Persisted canary readback established:

```text
DIRECT_QUERY_ATTEMPTS=4
BUYER_HABITAT_QUERY_ATTEMPTS=4
ADJACENT_QUERY_ATTEMPTS=4
DIRECT_RAW_SEARCH_RESULTS=7
BUYER_HABITAT_RAW_SEARCH_RESULTS=6
ADJACENT_RAW_SEARCH_RESULTS=6
DIRECT_TELEGRAM_LIKE_MATCHES=6
BUYER_HABITAT_TELEGRAM_LIKE_MATCHES=6
ADJACENT_TELEGRAM_LIKE_MATCHES=6
DIRECT_UNIQUE_CANDIDATE_SUPPORT=4
BUYER_HABITAT_UNIQUE_CANDIDATE_SUPPORT=3
ADJACENT_UNIQUE_CANDIDATE_SUPPORT=3
DIRECT_ONLY_CANDIDATES=1
MIXED_DIRECT_AND_NON_DIRECT_CANDIDATES=3
NON_DIRECT_ONLY_CANDIDATES=0
NON_DIRECT_SUPPORTED_UNIQUE_CANDIDATES=3
NON_DIRECT_LIVE_YIELD_PROVEN=YES
NON_DIRECT_ONLY_LIVE_YIELD_PROVEN=NO
NOVELTY_IMPROVED=NO
```

Required interpretation: buyer-habitat/adjacent supplied real live support to 3/4 unique candidates, but no non-direct-only candidate and no novelty improvement were observed in this bounded sample. Do not promote that evidence into a broader claim that search quality improved.

## Relevant candidate sources

The PR27 canary materialized four already-known sources. Sources `19` and `20` became the bounded Telegram targets because they were current candidates with non-direct support:

```text
SOURCE_19=@phystechcareerchannel
SOURCE_19_LIFECYCLE=candidate
SOURCE_19_SUPPORT=mixed_direct_and_non_direct

SOURCE_20=@juniors_rabota_jobs
SOURCE_20_LIFECYCLE=candidate
SOURCE_20_SUPPORT=mixed_direct_and_non_direct
```

No lifecycle decision has been made for either source.

## Telegram collector identity and controlled cleanup

Initial Telegram PRELIVE found two active collector rows:

```text
ACTIVE_TELEGRAM_COLLECTOR_COUNT=2
ACTIVE_TELEGRAM_COLLECTOR_IDS=1,2
DUPLICATE_ACTIVE_COLLECTOR_ROWS_PRESENT=YES
COLLECTOR_1_CLEANUP_COMPLETED=NO
```

Read-only evidence identified collector `2` as the historical production collector. Exact-head code supports multiple active rows because collector `ensure()` is scoped to `(platform, external_account_id)` and does not deactivate older identities.

A separately authorized identity-only gate then proved:

```text
CURRENT_SESSION_COLLECTOR_ACCOUNT_ID=2
CURRENT_SESSION_BINDING_PROVEN=YES
CURRENT_SESSION_MATCHES_HISTORICAL_PRODUCTION_COLLECTOR=YES
CURRENT_SESSION_IS_BOT=NO
COLLECTOR_ACCOUNT_MUTATION_PERFORMED=NO
DELTA_TELEGRAM_OPERATION_EVENTS=0
```

At the identity-only gate, collector `1` was still `is_active=true`; its exact historical Telegram-user origin was not proven.

After PR29 was reviewed, merged and synced to production, Owner separately authorized one controlled repository-API cleanup. It completed successfully:

```text
PRODUCTION_HEAD=c89e473fdd8895aefb7a0fac3a863468d56ab56e
REPOSITORY_API=CollectorAccountRepository.set_active
COLLECTOR_1_CONTROLLED_CLEANUP=PASS
COLLECTOR_1_CLEANUP_AUTHORIZATION_CONSUMED=YES
COLLECTOR_1_CLEANUP_COMPLETED=YES
COLLECTOR_1_IS_ACTIVE=NO
COLLECTOR_2_IS_ACTIVE=YES
ACTIVE_TELEGRAM_COLLECTOR_COUNT=1
ACTIVE_TELEGRAM_COLLECTOR_IDS=2
```

Collector `1` was deactivated, not deleted. Its operation-state row and historical references remain persisted. Collector `2` was not recreated and its proven session binding did not change. No Telegram, source, Web, AI, service or persistent-runtime action accompanied the cleanup.

## Bounded Telegram source access/freshness — completed

The next separate Owner authorization allowed one bounded probe through proven collector `2`:

```text
BOUNDED_TELEGRAM_PROBE_EXECUTION=PASS
IDENTITY_GUARD_COLLECTOR_2_MATCH=YES
MAX_GOVERNED_SOURCE_OPERATIONS=4
GOVERNED_SOURCE_OPERATIONS_ISSUED=4
FLOODWAIT_OCCURRED=NO
DELTA_TELEGRAM_OPERATION_EVENTS=4
NEW_OPERATION_EVENTS_ON_OTHER_COLLECTORS=0
```

Results:

```text
SOURCE_19_ENTITY_RESOLVED=YES
SOURCE_19_USERNAME_MATCH=YES
SOURCE_19_HISTORY_READ=YES
SOURCE_19_LATEST_MESSAGE_AT=2026-09-09T07:03:47+00:00
SOURCE_19_FRESH_WITHIN_10_DAYS=YES
SOURCE_19_LIFECYCLE=candidate

SOURCE_20_ENTITY_RESOLVED=YES
SOURCE_20_USERNAME_MATCH=YES
SOURCE_20_HISTORY_READ=YES
SOURCE_20_LATEST_MESSAGE_AT=2026-09-11T07:08:01+00:00
SOURCE_20_FRESH_WITHIN_10_DAYS=YES
SOURCE_20_LIFECYCLE=candidate
```

That specific access/freshness probe made no source/business mutation and sent no notification:

```text
OWNER_NOTIFICATIONS_SENT=0
JOIN_LEAVE_REQUESTS=0
LIFECYCLE_TRANSITIONS_PERFORMED=NO
SOURCE_VALIDATION_SERVICE_CALLED=NO
SOURCE_19_20_LIFECYCLE_DECISION=NONE
```

Access/freshness is distinct from lifecycle approval, Telegram membership, live-update readiness, Owner notification and persistent collection.

## Existing Owner notification rows — proven

A newly authorized bounded notification proof stopped in its read-only PRELIVE because durable terminal rows already existed for both targets:

```text
SOURCE_19_20_NOTIFICATION_PRELIVE=FAIL_PREEXISTING_DURABLE_ROWS
PRE_TARGET_OWNER_NOTIFICATION_COUNT=2
PRE_TARGET_ANY_RECIPIENT_NOTIFICATION_COUNT=2
TELEGRAM_NETWORK_ATTEMPTED=NO
CHECKPOINT_2_AUTHORIZED=NO
BOT_SEND_ATTEMPTS=0
OWNER_NOTIFICATIONS_SENT_BY_THIS_GATE=0
NOTIFICATION_PROOF_AUTHORIZATION_CONSUMED=NO
NOTIFICATION_PROOF_AUTHORIZATION_RETIRED_DUE_PREEXISTING_SENT_ROWS=YES
LIVE_CHECKPOINT_2_EXECUTED=NO
LIVE_CHECKPOINT_2_RETIRED=YES
RETRY_OR_LATE_CHECKPOINT2_ALLOWED=NO
```

The separate read-only diagnostic established:

```text
SOURCE_19_OWNER_CANDIDATE_NOTIFICATION=sent
SOURCE_20_OWNER_CANDIDATE_NOTIFICATION=sent
SOURCE_19_20_OWNER_NOTIFICATION_TO_CURRENT_OWNER=PROVEN
DURABLE_AT_MOST_ONCE_MARKERS_PRESENT=YES
REPEAT_NOTIFICATION_NEEDED=NO
REPEAT_NOTIFICATION_AUTHORIZED=NO
ROW_ORIGIN_EXACT_COMMAND_PROVABLE_FROM_SCHEMA=NO
ROW_ORIGIN_DIRECTLY_PERSISTED=NO
ATTRIBUTION_CLASS=TEMPORAL/STRUCTURAL_INFERENCE
```

The timestamps, nearby collector-`2` governor sequence and durable scan state are strongly compatible with the standard candidate-notification flow, but the schema does not persist the exact command, run, actor, process, collector FK or governor-event FK. Notification delivery is separate from lifecycle approval, membership, live-update readiness, Owner review, personalized opportunity delivery and recurring automation. Sources `19` and `20` remain `candidate` and unjoined.

## Current gate

```text
CURRENT_GATE=CANONICAL_DOCS_RECONCILIATION_AFTER_SOURCE_19_20_NOTIFICATION_DIAGNOSTIC
NEXT_GATE=INDEPENDENT_REVIEW_OF_EXACT_DOCS_HEAD
NEW_LIVE_ACTION_AUTHORIZED=NO
PERSISTENT_RUNTIME_AUTHORIZED=NO
CANDIDATE_NOTIFICATION_RECURRING_AUTOMATION_AUTHORIZED=NO
```

## Required sequence from here

```text
1. reconcile canonical docs with source 19/20 notification-row evidence
2. independent review of the exact docs head
3. Owner merge authorization
4. merge the exact reviewed docs head
5. docs-only production sync / exact-head reconciliation as required
6. only then choose one new, separate Owner-authorized gate
```

The next live/mutating gate is intentionally **not selected yet**. Reasonable future candidates remain independent choices:

```text
manual/reviewed lifecycle decision for source 19/20
membership provisioning if/after a source is approved
persistent runtime only much later
```

None of those is authorized by this docs reconciliation. The prior notification-proof live checkpoint is retired and must not be executed or retried.

## Operational source-of-truth rule

For any future production task preserve:

```text
fresh exact-head server evidence
> exact code / CLI behavior
> canonical docs
> historical reports
```

Do not infer authorization from a successful prior bounded gate.

## Later product target

Once source quality, lifecycle decisions, membership and delivery behavior have been separately proven, the intended unattended candidate-notification behavior remains:

```text
every 3 hours
one pass
max 5 new cards
silence if none
durable at-most-once
never notify the same candidate twice
```

This target is not current production authorization.
