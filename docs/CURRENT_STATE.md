# LeadRadar — Current State

**Status:** CANONICAL  
**Snapshot date:** 2026-09-11
**Implementation baseline:** `81a675b72ed4c1229cedad28e5d2e1f56bac1f66`
**Current deployed repository head:** `81a675b72ed4c1229cedad28e5d2e1f56bac1f66`

## Executive status

LeadRadar production is stable at the merged PR27 commit. PR23 restored SearXNG by preserving inherited engine/network definitions and disabling the exact unwanted engines. PR24 changed profile Web query rendering for `buyer_habitat` and `adjacent` without changing the bounded planner contract. PR27 versioned the immutable Profile Discovery Intent contract to `profile-discovery-intent.v2`.

PR24 production sync, post-sync verification and full bounded offline Stage A all passed.

PR25/PR26 documentation changes were carried by the PR27 production sync. PR27 production sync, post-sync verification, and the technical read-only PRELIVE for the repaired profile-discovery path all passed.

Current proven bounded planner fingerprint:

```text
generated=36
exact_duplicates=0
near_duplicates=2
executable=34
selected=12
selected_direct=4
selected_buyer_habitat=4
selected_adjacent=4
```

PR24/PR27 live Web yield improvement is **not yet proven**. No live Web canary has been authorized or issued after the PR27 production sync. The technical PRELIVE passed without Web, Telegram, AI, database-write, service-restart, runtime-env, or persistent-runtime side effects.

Persistent LeadRadar runtime, Telegram candidate validation and unattended discovery remain unauthorized.

## Production contract

```text
PRODUCTION_HEAD=81a675b72ed4c1229cedad28e5d2e1f56bac1f66
BRANCH=main
TRACKED_WORKTREE=CLEAN
PYTHON_VERSION=3.14.7
PRODUCTION_PYTHON=./.venv/bin/python
BARE_PYTHON=ABSENT
ALEMBIC_CURRENT=20260908_0042
PERSISTENT_RUNTIME=STOPPED
PROFILE_DISCOVERY_INTENT_VERSION=profile-discovery-intent.v2
```

CLI namespaces are distinct:

```text
APPLICATION_CLI=./.venv/bin/python -m freelancer_bot
OPERATOR_CLI=./.venv/bin/python -m freelancer_bot.operator_cli
```

Profile Web Discovery belongs to the operator CLI:

```text
./.venv/bin/python -m freelancer_bot.operator_cli profile-discovery run ...
```

The complete operational contract is canonical in [`OPERATIONS.md`](OPERATIONS.md).

## Runtime services

Verified production topology:

```text
PostgreSQL:
  container=leadradar-postgres
  image=postgres:18.4-alpine
  port=127.0.0.1:55432->5432/tcp
  state=healthy

SearXNG:
  container=freelancer-lead-bot-searxng-1
  image_id_prefix=892cf8093419
  port=127.0.0.1:8888->8080/tcp
  endpoint=http://127.0.0.1:8888
  state=running

Vaultwarden no-touch neighbor:
  container=vaultwarden
  image=vaultwarden/server:latest
  port=127.0.0.1:8080->80/tcp
  state=healthy
```

SearXNG exact engine strategy:

```yaml
use_default_settings: true

engines:
  - name: brave
    disabled: true
  - name: duckduckgo
    disabled: true
  - name: startpage
    disabled: true
```

The historical destructive `engines.remove` approach is invalid for the pinned image because retained variants depend on the `brave` network alias.

## Runtime safety state

Verified production values:

```text
SOURCE_DISCOVERY_ENABLED=false
SOURCE_AUDIT_ENABLED=false
TELEGRAM_GLOBAL_DISCOVERY_ENABLED=false
SOURCE_GRAPH_DISCOVERY_ENABLED=false
AI_REPLY_ENABLED=false
SEARXNG_PORT=8888
SEARXNG_URL=http://127.0.0.1:8888
DATABASE_URL_CONFIGURED=YES
```

The canonical runtime env must be loaded before DB-connected Alembic commands.

## Database operational contract

LeadRadar uses SQLAlchemy async connections:

```text
Database.connect() -> sqlalchemy.ext.asyncio.AsyncConnection
query API -> connection.execute(...) / connection.scalar(...)
```

Verified source lifecycle field:

```text
sources.lifecycle_status
candidate=candidate
```

Verified read-only inventory snapshot from the operational-contract discovery:

```text
DISCOVERY_RUN_COUNT=6
SOURCE_COUNT=22
CANDIDATE_COUNT=7
OWNER_NOTIFICATION_COUNT=3
TELEGRAM_OPERATION_EVENT_COUNT=203
AI_CALL_TELEMETRY_COUNT=51
SOURCE_LIFECYCLE_EVENT_COUNT=24
```

Counts are observational snapshots, not stable invariants.

## PR23 bounded Web baseline

The comparable pre-PR24 canary completed successfully:

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

This remains the comparison baseline for the next PR24 live run.

## PR24 state

```text
PR24_MERGED=YES
PR24_REVIEWED_HEAD=6280c569516fdd586dd467ec2c507b816bbde844
PR24_MERGE_COMMIT=1299e64f28886dffe3b4bb0ddc201952aa8a2a28
PR24_PRODUCTION_SYNC=PASS
PR24_POST_SYNC_VERIFICATION=PASS
PR24_FULL_STAGE_A_OFFLINE=PASS
PR24_LIVE_YIELD_IMPROVEMENT_PROVEN=NO
PR24_WEB_CANARY_READ_ONLY_PRELIVE=PASS
```

The attempted live command using `python -m freelancer_bot profile-discovery run ...` was rejected by the application CLI parser. Because the invocation was issued under a one-attempt authorization, that authorization is consumed even though actual Web execution did not begin.

The subsequent correctly namespaced live invocation consumed a fresh authorization and failed before Web discovery run creation:

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

The attempted run key is retired operationally despite no `discovery_runs` row:

```text
RETIRED_RUN_KEY=owner-profile-web-pr24-bounded-20260911-v1
RETIRED_RUN_KEY_STATUS=RETIRED_DO_NOT_REUSE
```

## PR27 production sync and PRELIVE state

```text
PR27_REVIEWED=PASS
PR27_REVIEWED_HEAD=c09f3a501cd554a931531b14e8fd84aeda94d90a
PR27_MERGE_COMMIT=81a675b72ed4c1229cedad28e5d2e1f56bac1f66
PR27_PRODUCTION_SYNC=PASS
PR27_POST_SYNC_VERIFICATION=PASS
PR27_TECHNICAL_PRELIVE=PASS
PR25_PR26_DOCS_SYNCED_WITH_PR27=YES

PR25_REVIEWED=PASS
PR25_REVIEWED_HEAD=c0951e2e0400d1e3489bdb91b353b71e83139b5f
PR25_MERGED=YES
PR25_MERGE_COMMIT=da5eda8753f3bf48f14dfbcbeaa480159951a739
PR25_PRODUCTION_DOCS_SYNC=CARRIED_BY_PR27
```

Technical PRELIVE repaired-path evidence:

```text
CHECKPOINT_4R=PASS
PROFILE_ID=e3f2a0d1-3a46-4506-8a79-f4ed47400279
PROFILE_REVISION=8
PROFILE_ACTIVE=YES
PROFILE_PRIMARY=YES
PROFILE_CONFIRMATION_STATUS=confirmed
CURRENT_INTENT_ID=b3f53d57-afd9-55e1-b822-77d687fe466d
CURRENT_INTENT_VERSION=profile-discovery-intent.v2
CURRENT_GENERATED_WEB_QUERY_COUNT=36
PERSISTED_INTENT_ROW_COUNT=1
PERSISTED_V1_COUNT=1
HISTORICAL_V1_INTENT_ID=503e6238-1896-5d4a-84b1-004487d56c97
CURRENT_V2_DISTINCT_FROM_V1=YES
PERSISTED_V2_COUNT=0
PERSISTED_V2_INTENT_ID=NONE
CURRENT_V2_CONFLICT_PRESENT=NO
```

This is expected safe Case A: historical v1 remains immutable, current v2 has a distinct deterministic identity, and no v2 row exists until the first authorized v2 discovery execution persists it.

Technical PRELIVE gate evidence:

```text
PARSER_ONLY=PASS
PROPOSED_RUN_KEY=owner-profile-web-pr27-bounded-20260911-v1
RUN_KEY_UNUSED=YES
SEARXNG_EFFECTIVE_STATE=READY
PROVIDER_HEALTH_BLOCKER=NO
PROVIDER_HEALTH_GATE=PASS
BASELINE_COUNTERS_CAPTURED=YES
DISCOVERY_RUN_COUNT=6
SOURCE_COUNT=22
CANDIDATE_COUNT=7
OWNER_NOTIFICATION_COUNT=3
TELEGRAM_OPERATION_EVENT_COUNT=203
AI_CALL_TELEMETRY_COUNT=51
SOURCE_LIFECYCLE_EVENT_COUNT=24
DB_WRITES_PERFORMED=NO
WEB_REQUESTS_PERFORMED=NO
TELEGRAM_REQUESTS_PERFORMED=NO
AI_REQUESTS_PERFORMED=NO
```

## Current authorization state

```text
PERSISTENT_SOURCE_DISCOVERY_AUTHORIZED=NO
TELEGRAM_DISCOVERY_AUTHORIZED=NO
SOURCE_AUDIT_AUTHORIZED=NO
AUTO_APPROVE_AUTHORIZED=NO
AUTO_JOIN_AUTHORIZED=NO
TELEGRAM_CANDIDATE_VALIDATION_AUTHORIZED=NO
PERSISTENT_RUNTIME_AUTHORIZED=NO
NEW_PR24_WEB_CANARY_AUTHORIZED=NO
NEW_PR27_WEB_CANARY_AUTHORIZED=NO
WEB_DISCOVERY_EXECUTED_AFTER_PR27_SYNC=NO
```

## Next gate

The next step is canonical documentation reconciliation after PR27 production sync and technical PRELIVE. Technical PRELIVE pass is not live Web authorization.

```text
CANONICAL_DOCS_RECONCILIATION_AFTER_PR27_PRELIVE
-> independent review of exact docs head
-> Owner merge authorization
-> merge exact reviewed head
-> separate docs-only production sync authorization
-> minimum final read-only live-gate refresh
-> confirm exact production HEAD / clean worktree / runtime stopped
-> confirm proposed run key remains unused
-> confirm provider health remains non-blocking
-> confirm exact future argv remains valid if code changed
-> fresh explicit one-attempt Owner authorization
-> exactly one bounded Web-only canary
-> no retry under the same authorization
-> compare non-direct yield and novelty against PR23
-> only then decide whether Telegram validation is justified
```

Provider-health preflight must follow runtime semantics: `UNAVAILABLE` blocks; an active `BACKOFF` with `backoff_until > now` blocks; an expired `BACKOFF` is effectively `DEGRADED` and is not a blocker by itself; `DEGRADED` alone is not a blocker; `READY` passes.

Useful owner delivery and persistent unattended operation remain later gates.
