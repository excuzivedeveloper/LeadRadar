# LeadRadar — Active Plan

**Status:** CANONICAL / ACTIVE  
**Last verified:** 2026-09-11
**Implementation baseline:** `81a675b72ed4c1229cedad28e5d2e1f56bac1f66`

This file defines execution order. Implemented capability does not imply authorization to activate it.

## Current production baseline

```text
PRODUCTION_HEAD=81a675b72ed4c1229cedad28e5d2e1f56bac1f66
BRANCH=main
TRACKED_WORKTREE=CLEAN
ALEMBIC_CURRENT=20260908_0042
PERSISTENT_RUNTIME=STOPPED
PROFILE_DISCOVERY_INTENT_VERSION=profile-discovery-intent.v2
```

Verified service state:

```text
POSTGRES=running healthy on 127.0.0.1:55432
SEARXNG=running on 127.0.0.1:8888
VAULTWARDEN=running healthy on 127.0.0.1:8080 and NO-TOUCH
```

Verified safety state:

```text
SOURCE_DISCOVERY_ENABLED=false
SOURCE_AUDIT_ENABLED=false
TELEGRAM_GLOBAL_DISCOVERY_ENABLED=false
SOURCE_GRAPH_DISCOVERY_ENABLED=false
AI_REPLY_ENABLED=false
PERSISTENT_RUNTIME_AUTHORIZED=NO
TELEGRAM_CANDIDATE_VALIDATION_AUTHORIZED=NO
```

## Completed current chain

```text
PR23_MERGED=YES
PR23_PRODUCTION_SYNCED=YES
PR23_SEARXNG_RECOVERY=PASS
PR23_BOUNDED_WEB_CANARY=PASS

PR24_MERGED=YES
PR24_REVIEWED_HEAD=6280c569516fdd586dd467ec2c507b816bbde844
PR24_MERGE_COMMIT=1299e64f28886dffe3b4bb0ddc201952aa8a2a28
PR24_PRODUCTION_SYNC=PASS
PR24_POST_SYNC_VERIFICATION=PASS
PR24_FULL_BOUNDED_STAGE_A_OFFLINE=PASS

PR25_REVIEWED=PASS
PR25_REVIEWED_HEAD=c0951e2e0400d1e3489bdb91b353b71e83139b5f
PR25_MERGED=YES
PR25_MERGE_COMMIT=da5eda8753f3bf48f14dfbcbeaa480159951a739
PR25_PRODUCTION_DOCS_SYNC=CARRIED_BY_PR27

PR27_REVIEWED=PASS
PR27_REVIEWED_HEAD=c09f3a501cd554a931531b14e8fd84aeda94d90a
PR27_MERGE_COMMIT=81a675b72ed4c1229cedad28e5d2e1f56bac1f66
PR27_PRODUCTION_SYNC=PASS
PR27_POST_SYNC_VERIFICATION=PASS
PR27_TECHNICAL_PRELIVE=PASS
```

PR25/PR26 documentation changes were carried by the PR27 production sync. The
production checkout is now at the PR27 merge commit.

PR24 preserved the bounded planner contract:

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

PR24 angle-aware query rendering is active offline:

```text
DIRECT_QUERY_PRECISION_SHAPE=PASS
BUYER_HABITAT_RELAXED_SHAPE=PASS
ADJACENT_RELAXED_SHAPE=PASS
RU_BUYER_HABITAT_CONTEXT=PASS
RU_ADJACENT_CONTEXT=PASS
SITE_T_ME_RESTRICTION_PRESERVED=YES
```

## Pre-PR24 live comparison baseline

```text
RUN_KEY=owner-profile-web-pr23-bounded-20260910-v1
DISCOVERY_RUN_ID=50de44e5-1b17-4f08-9a12-86b6d899f4ab
GENERATED=36
EXECUTABLE=34
SELECTED=12
EXECUTED=12
SEARCH_RESULTS_CONSIDERED=7
TELEGRAM_LIKE_RESULTS=6
UNIQUE_CANDIDATES=4
KNOWN_CANDIDATES=4
NEW_CANDIDATES=0
PROVIDER_DEGRADED=NO
PROVIDER_BACKOFF=NO
BACKEND_FAILURES=0
USEFUL_YIELD_ANGLE=direct_only
```

## Failed PR24 live attempts and intent-version blocker

A later PR24 canary authorization was consumed by an invocation that used the wrong CLI namespace:

```text
WRONG=./.venv/bin/python -m freelancer_bot profile-discovery run ...
CORRECT_NAMESPACE=./.venv/bin/python -m freelancer_bot.operator_cli ...
```

Observed outcome:

```text
WORKFLOW_STATUS=CLI_ARGUMENT_REJECTED
ACTUAL_WEB_DISCOVERY_EXECUTION=NO
DISCOVERY_RUN_ID=NONE
SEARCH_RESULTS_CONSIDERED=0
LIVE_TELEGRAM_CALLS=0
LIVE_AI_CALLS=0
```

This event is not evidence about SearXNG/provider stability or PR24 live yield.

A subsequent read-only PRELIVE for the corrected operator namespace passed:

```text
PR24_WEB_CANARY_READ_ONLY_PRELIVE=PASS
```

The correctly namespaced authorized live invocation then failed before
`discovery_runs` creation:

```text
RUN_KEY=owner-profile-web-pr24-bounded-20260911-v1
LIVE_INVOCATION_ISSUED=YES
AUTHORIZATION_CONSUMED=YES
PRIMARY_LIVE_FAILURE_TYPE=RuntimeError
PRIMARY_LIVE_FAILURE=profile discovery intent identity has conflicting content
DISCOVERY_RUN_CREATED=NO
CANARY_EVIDENCE_CAPTURE=INCOMPLETE
```

A second Web invocation was accidentally issued and returned the same error:

```text
LIVE_COMMAND_ATTEMPTS=2
AUTHORIZED_LIVE_COMMAND_ATTEMPTS=1
SECOND_WEB_ATTEMPT_PERFORMED=YES
SECOND_WEB_ATTEMPT_AUTHORIZED=NO
```

Do not treat that second invocation as a valid retry. One-attempt authorization
is consumed when the invocation command is issued, even if discovery does not
reach provider execution.

Root-cause evidence:

```text
DETERMINISTIC_ID_MATCH=YES
DIFFERING_FIELD_COUNT=1
DIFFERING_FIELDS=generated_web_queries
ONLY_GENERATED_WEB_QUERIES_DIFFER=YES
SOURCE_PROFILE_RELEVANCE_REF_COUNT=19
DISCOVERY_RUN_INTENT_REF_COUNT=4
PR24_QUERY_RENDERING_CONFLICT_HYPOTHESIS=SUPPORTED
```

The old run key is retired operationally because it was already used in the
authorized invocation sequence and then in the unauthorized second invocation:

```text
RETIRED_RUN_KEY=owner-profile-web-pr24-bounded-20260911-v1
RETIRED_RUN_KEY_STATUS=RETIRED_DO_NOT_REUSE
NEW_PR24_WEB_CANARY_AUTHORIZED=NO
TELEGRAM_CANDIDATE_VALIDATION_AUTHORIZED=NO
PERSISTENT_RUNTIME_AUTHORIZED=NO
```

PR27 repaired the root cause by versioning the immutable Profile Discovery
Intent contract to `profile-discovery-intent.v2`. Technical read-only PRELIVE
then passed without issuing live Web, Telegram, or AI work:

```text
CHECKPOINT_4R=PASS
CURRENT_INTENT_ID=b3f53d57-afd9-55e1-b822-77d687fe466d
HISTORICAL_V1_INTENT_ID=503e6238-1896-5d4a-84b1-004487d56c97
CURRENT_V2_DISTINCT_FROM_V1=YES
PERSISTED_V2_COUNT=0
CURRENT_V2_CONFLICT_PRESENT=NO
TECHNICAL_PRELIVE=PASS
PARSER_ONLY=PASS
PROPOSED_RUN_KEY=owner-profile-web-pr27-bounded-20260911-v1
RUN_KEY_UNUSED=YES
SEARXNG_EFFECTIVE_STATE=READY
PROVIDER_HEALTH_GATE=PASS
BASELINE_COUNTERS_CAPTURED=YES
WEB_REQUESTS_PERFORMED=NO
TELEGRAM_REQUESTS_PERFORMED=NO
AI_REQUESTS_PERFORMED=NO
DB_WRITES_PERFORMED=NO
```

## Operational contract gate

A full read-only production operational inventory has passed and established:

```text
PRODUCTION_PYTHON=./.venv/bin/python
PYTHON_VERSION=3.14.7
BARE_PYTHON=ABSENT
APPLICATION_CLI=./.venv/bin/python -m freelancer_bot
OPERATOR_CLI=./.venv/bin/python -m freelancer_bot.operator_cli
PROFILE_DISCOVERY_RUN_PRESENT=YES
DB_CONNECTION_LAYER=SQLALCHEMY_ASYNC
DB_QUERY_API=execute+scalar
SOURCES_LIFECYCLE_COLUMN=lifecycle_status
SOURCE_CANDIDATE_VALUE=candidate
ALEMBIC_REQUIRES_CANONICAL_ENV_LOADED=YES
OPERATIONAL_CONTRACT_DISCOVERY=PASS
```

The canonical command/runbook surface is recorded in `docs/OPERATIONS.md` and PR25 has been independently reviewed and merged.

## Current gate

```text
CURRENT_GATE=CANONICAL_DOCS_RECONCILIATION_AFTER_PR27_PRELIVE
NEXT_GATE=INDEPENDENT_REVIEW_OF_DOCS_RECONCILIATION
NEW_PR27_WEB_CANARY_AUTHORIZED=NO
```

## Required sequence from here

```text
1. reconcile canonical docs with PR27 production sync and technical PRELIVE
2. independent review of exact docs head
3. Owner merge authorization
4. merge exact reviewed docs head
5. separate controlled docs-only production sync
6. minimum final read-only live-gate refresh
7. reverify exact production HEAD, clean worktree and runtime stopped
8. reverify proposed run key remains unused
9. reverify provider health remains non-blocking
10. revalidate exact future argv if code changed
11. fresh explicit one-attempt Owner Web authorization
12. exactly one bounded Web-only canary
13. no retry
14. compare PR24 buyer_habitat/adjacent yield and novelty against PR23 baseline
15. Telegram validation remains a separate later gate
16. persistent unattended runtime remains unauthorized until useful end-to-end behavior is proven
```

The docs reconciliation does not authorize live Web work. The PR27 technical
PRELIVE passed, but time-sensitive live-gate facts still require a final
read-only refresh immediately before any fresh one-attempt Owner authorization.

Effective persisted Web provider health must be interpreted using runtime semantics:

```text
UNAVAILABLE -> BLOCK
BACKOFF with backoff_until > now -> BLOCK
BACKOFF with backoff_until <= now -> not a blocker; effective state is DEGRADED
DEGRADED -> not a blocker by itself
READY -> PASS
```

## Next bounded Web canary requirements

Do not create or execute the live canary until this docs reconciliation is
reviewed, merged, docs-synced to production, and the final read-only live-gate
refresh passes with a fresh Owner authorization granted.

The canary must use the operator CLI namespace:

```text
./.venv/bin/python -m freelancer_bot.operator_cli profile-discovery run ...
```

It must use:

```text
PROFILE_ID=e3f2a0d1-3a46-4506-8a79-f4ed47400279
PROFILE_REVISION=8
MAX_QUERIES=12
RESULTS_PER_QUERY=3
MAX_CANDIDATES=10
SEARXNG_URL=http://127.0.0.1:8888
PROPOSED_RUN_KEY=owner-profile-web-pr27-bounded-20260911-v1
PROPOSED_RUN_KEY_STATUS=FRESH_UNUSED_NOT_AUTHORIZED
RETIRED_RUN_KEY=owner-profile-web-pr24-bounded-20260911-v1
RUN_COMMAND_ATTEMPTS_MAX=1
CANARY_RETRY_ALLOWED=NO
```

The exact future argv parser-only check already passed during technical
PRELIVE. Repeat parser-only validation during final live-gate refresh if code
has changed before live authorization.

A new Owner authorization is required. The previous PR24 authorization is
consumed and must not be reused.

<!-- Historical sequence retained below for context: PR27 has completed these steps. -->
```text
1. independent review of exact profile-discovery intent-version fix head
2. Owner merge authorization
3. merge exact reviewed head
4. separate Owner authorization for production sync
5. fast-forward production to the exact authorized merge target
6. read-only post-sync verification
7. read-only PRELIVE for the repaired profile-discovery path
8. prove current v2 intent identity no longer conflicts with historical v1
9. choose a NEW fresh Web canary run key
10. only after PRELIVE PASS: obtain a NEW one-attempt Owner authorization
11. exactly one bounded Web-only canary
12. no retry
13. compare PR24 buyer_habitat/adjacent yield and novelty against PR23 baseline
14. Telegram validation remains a separate later gate
15. persistent unattended runtime remains unauthorized until useful end-to-end behavior is proven
```

## Later product target

Once search quality and Telegram validation are proven, the intended unattended candidate-notification behavior remains:

```text
every 3 hours
one pass
max 5 new cards
silence if none
durable at-most-once
never notify the same candidate twice
```

This target is not current production authorization.
