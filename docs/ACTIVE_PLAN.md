# LeadRadar — Active Plan

**Status:** CANONICAL / ACTIVE  
**Last verified:** 2026-09-10  
**Implementation baseline:** `1299e64f28886dffe3b4bb0ddc201952aa8a2a28`

This file defines execution order. Implemented capability does not imply authorization to activate it.

## Current production baseline

```text
PRODUCTION_HEAD=1299e64f28886dffe3b4bb0ddc201952aa8a2a28
BRANCH=main
TRACKED_WORKTREE=CLEAN
ALEMBIC_CURRENT=20260908_0042
PERSISTENT_RUNTIME=STOPPED
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
```

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

## Failed PR24 live attempt classification

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

## Operational contract gate

A full read-only production operational inventory has now passed and established:

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

The canonical command/runbook surface is being recorded in `docs/OPERATIONS.md` before any new live canary.

## Current gate

```text
CURRENT_GATE=CANONICAL_OPERATIONS_DOCUMENTATION
NEXT_GATE=INDEPENDENT_REVIEW_CANONICAL_OPERATIONS_DOCS
```

## Required sequence from here

```text
1. complete docs-only canonical operations PR
2. independent review of exact docs PR head
3. only if PASS: Owner merge authorization
4. merge exact reviewed docs head
5. sync docs-only merge to production checkout separately if needed
6. derive next canary command from docs/OPERATIONS.md and exact operator CLI --help
7. create fresh Owner authorization with a fresh run key
8. execute exactly one bounded PR24 Web-only canary
9. compare buyer_habitat/adjacent yield and candidate novelty against PR23 baseline
10. only if useful/new Web candidates justify it, design a separate Telegram validation gate
11. persistent unattended runtime remains unauthorized until useful end-to-end behavior is proven
```

## Next PR24 live canary requirements

Do not create or execute this canary until the docs gate above is complete.

The next canary must use the operator CLI namespace:

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
FRESH_RUN_KEY=REQUIRED
RUN_COMMAND_ATTEMPTS_MAX=1
CANARY_RETRY_ALLOWED=NO
```

A new Owner authorization is required. The previous authorization is consumed and must not be reused.

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
