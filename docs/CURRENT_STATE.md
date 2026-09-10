# LeadRadar — Current State

**Status:** CANONICAL  
**Snapshot date:** 2026-09-10  
**Implementation baseline:** `1299e64f28886dffe3b4bb0ddc201952aa8a2a28`  
**Current deployed repository head:** `1299e64f28886dffe3b4bb0ddc201952aa8a2a28`

## Executive status

LeadRadar production is stable at the merged PR24 commit. PR23 restored SearXNG by preserving inherited engine/network definitions and disabling the exact unwanted engines. PR24 changed profile Web query rendering for `buyer_habitat` and `adjacent` without changing the bounded planner contract.

PR24 production sync, post-sync verification and full bounded offline Stage A all passed.

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

PR24 live yield improvement is **not yet proven**. The first attempted PR24 live canary did not reach Web Discovery because the wrong CLI namespace was invoked. It therefore provides no evidence about provider/SearXNG quality, non-direct yield or candidate novelty.

Persistent LeadRadar runtime, Telegram candidate validation and unattended discovery remain unauthorized.

## Production contract

```text
PRODUCTION_HEAD=1299e64f28886dffe3b4bb0ddc201952aa8a2a28
BRANCH=main
TRACKED_WORKTREE=CLEAN
PYTHON_VERSION=3.14.7
PRODUCTION_PYTHON=./.venv/bin/python
BARE_PYTHON=ABSENT
ALEMBIC_CURRENT=20260908_0042
PERSISTENT_RUNTIME=STOPPED
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
```

The attempted live command using `python -m freelancer_bot profile-discovery run ...` was rejected by the application CLI parser. Because the invocation was issued under a one-attempt authorization, that authorization is consumed even though actual Web execution did not begin.

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
```

## Next gate

Documentation must be reviewed and merged before a new live canary is planned.

```text
CANONICAL_OPERATIONS_DOCUMENTATION
-> INDEPENDENT_DOCS_REVIEW
-> OWNER_MERGE_AUTHORIZATION
-> merge exact reviewed docs head
-> separate production docs sync if required
-> derive canary from canonical OPERATIONS.md + exact operator CLI --help
-> fresh Owner authorization
-> exactly one new bounded PR24 Web-only canary with a fresh run key
-> compare non-direct yield and novelty against PR23
-> only then decide whether Telegram validation is justified
```

Useful owner delivery and persistent unattended operation remain later gates.
