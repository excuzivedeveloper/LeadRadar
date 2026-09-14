# LeadRadar — Production Operations

**Status:** CANONICAL  
**Last verified:** 2026-09-12
**Implementation baseline:** `b3bb1f6266fe3f7dd17cd81329dc6689ceadcfe2`
**Latest verified production evidence head:** `b660bdd633137f13dae5a8524f14d36c0f5ecd05`

This document is the operational source of truth for the current LeadRadar production environment. Fresh exact-head server evidence outranks this document; if later evidence disagrees, stop and reconcile docs before designing a new live task.

## 1. Production layout

```text
checkout=/opt/leadradar/LeadRadar
runtime_env=/opt/leadradar/runtime/.env
runtime_sessions=/opt/leadradar/runtime/sessions/
venv=/opt/leadradar/LeadRadar/.venv
python=./.venv/bin/python
python_version=3.14.7
bare_python=ABSENT
alembic_current=20260908_0042
latest_verified_production_evidence_head=b660bdd633137f13dae5a8524f14d36c0f5ecd05
implementation_baseline=81a675b72ed4c1229cedad28e5d2e1f56bac1f66
```

Do not modify global Python for LeadRadar work.

## 2. Runtime topology

Verified production services:

```text
PostgreSQL:
  container=leadradar-postgres
  image=postgres:18.4-alpine
  host_bind=127.0.0.1:55432->5432/tcp
  health=healthy

SearXNG:
  container=freelancer-lead-bot-searxng-1
  image_id_prefix=892cf8093419
  pinned_image=searxng/searxng@sha256:892cf809341915a4b7710d3c9045005b4c377d51335a089b6d4da0b28750788d
  endpoint=http://127.0.0.1:8888
  host_bind=127.0.0.1:8888->8080/tcp
  host_settings=config/searxng/settings.yml
  container_settings=/etc/searxng/settings.yml
  settings_mount=read-only
  runtime_interpreter=/usr/local/searxng/.venv/bin/python3

Vaultwarden no-touch neighbor:
  container=vaultwarden
  image=vaultwarden/server:latest
  host_bind=127.0.0.1:8080->80/tcp
  health=healthy
```

Persistent LeadRadar application runtime is not authorized and must remain stopped outside a separately authorized runtime gate.

## 3. Canonical runtime safety flags

Expected current values in `/opt/leadradar/runtime/.env`:

```text
SOURCE_DISCOVERY_ENABLED=false
SOURCE_AUDIT_ENABLED=false
TELEGRAM_GLOBAL_DISCOVERY_ENABLED=false
SOURCE_GRAPH_DISCOVERY_ENABLED=false
AI_REPLY_ENABLED=false
SEARXNG_PORT=8888
SEARXNG_URL=http://127.0.0.1:8888
DATABASE_URL=configured
```

Never print `DATABASE_URL`, Telegram credentials, API keys, session contents, owner numeric Telegram ID, login codes, or live message bodies.

## 4. Python entrypoints

There are two different CLI namespaces. Do not interchange them.

### Application/runtime CLI

```bash
./.venv/bin/python -m freelancer_bot --help
```

### Operator CLI

```bash
./.venv/bin/python -m freelancer_bot.operator_cli --help
```

Profile Web Discovery lives under the operator CLI:

```bash
./.venv/bin/python -m freelancer_bot.operator_cli \
  profile-discovery run \
  --profile-id <UUID> \
  --run-key <UNIQUE_RUN_KEY> \
  --searxng-url http://127.0.0.1:8888 \
  --results-per-query <N> \
  --max-candidates <N> \
  --max-queries <N>
```

`--max-queries` bounds only that explicit one-shot invocation. It does not bound or authorize persistent runtime.

Before a future live run, verify the exact command contract from exact-head code and parser-only validate the exact future argv without dispatch. Parser acceptance proves only the argparse contract; profile state, run-key freshness, provider health, authorization and all other gates remain separate.

## 5. Operator CLI command catalog and side-effect classes

Current command families include:

```text
collectors
  status
telegram-discovery
  status
  topics
  run
  screen-pending
sources
  list
  show
  audits
  transition
discovery
  web
  graph
  runs
  results
audit
  run
  re-audit
  list
match
  runs
  traces
delivery
  list
observe
  raw
  opportunities
  metrics
profile-discovery
  evaluate
  canary
  run
  coverage
  intents
  calibrate
source-bootstrap
  start
  status
  pause
  resume
  run
source-library
  stats
  coverage
  validate
  validate-candidates
  query-dedup
  backfill-legacy-evidence
  rerank-candidates
  offline-scale
```

Treat commands by actual side effect, not by name:

```text
READ-ONLY / OFFLINE candidates:
  --help
  collectors status
  telegram-discovery status/topics
  sources list/show/audits
  discovery runs/results
  audit list
  match runs/traces
  delivery list
  observe raw/opportunities/metrics
  profile-discovery coverage/intents/calibrate
  source-bootstrap status
  source-library stats/coverage/query-dedup/offline-scale

LIVE WEB / PERSISTENCE:
  discovery web
  profile-discovery evaluate/canary/run
  source-bootstrap run

TELEGRAM / EXTERNAL STATE:
  telegram-discovery run/screen-pending
  discovery graph
  source-library validate/validate-candidates

EXPLICIT MUTATION:
  sources transition
  audit run/re-audit
  source-bootstrap start/pause/resume
  source-library backfill-legacy-evidence
  source-library rerank-candidates
```

Before using any command in production, inspect its implementation and `--help` at the exact target commit.

## 6. Database contract

LeadRadar uses SQLAlchemy async connections:

```text
Database.connect() -> sqlalchemy.ext.asyncio.AsyncConnection
read API -> connection.execute(...) / connection.scalar(...)
```

Do not assume asyncpg `fetchval`, `fetchrow`, or `fetch` methods unless the exact code path explicitly returns asyncpg.

Verified source lifecycle field and candidate value:

```text
sources.lifecycle_status
SourceStatus.CANDIDATE="candidate"
```

Verified operational schema symbols include:

```text
discovery_runs
sources
owner_source_candidate_notifications
telegram_collector_operation_events
ai_call_telemetry
source_lifecycle_events
```

The bounded Owner candidate-notification selector at the implementation
baseline is fail closed and requires the configured Owner's exact active,
primary, confirmed PostgreSQL SearchProfile and its deterministic current
Profile Discovery Intent. Candidate SQL requires an exact
`source_profile_relevance` row for that profile, intent, revision, and
`relevance_class=strong` before applying `LIMIT`. Weak, adequate, historical,
other-profile, old-revision, and missing-current-relevance rows cause no
Telegram probe, reservation, or send. The durable recipient/source dedupe,
cursor wrap, 10-day Telegram activity boundary, safe URL check, identity race
guard, and open-only card remain unchanged.

This implementation does not authorize a one-shot run, recurring schedule,
Source Audit, discovery, AI, lifecycle mutation, membership action, or
persistent runtime.

Latest bounded evidence snapshot:

```text
DISCOVERY_RUN_COUNT=7
SOURCE_COUNT=22
CANDIDATE_COUNT=7
OWNER_NOTIFICATION_COUNT=3
TELEGRAM_OPERATION_EVENT_COUNT=207
AI_CALL_TELEMETRY_COUNT=51
SOURCE_LIFECYCLE_EVENT_COUNT=24
```

Counts are snapshots, not invariants.

## 7. Alembic contract

`alembic.ini` does not carry the production DSN. Production DB-connected Alembic commands require the canonical runtime env:

```bash
cd /opt/leadradar/LeadRadar
set -a
. /opt/leadradar/runtime/.env
set +a
./.venv/bin/alembic current
```

Expected current revision:

```text
20260908_0042
```

Never run `alembic upgrade` or `downgrade` without a separate migration authorization.

## 8. SearXNG operational contract

Current effective strategy:

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

Do not remove these base engine definitions. Retained variants depend on shared network aliases; destructive removal historically caused `KeyError: 'brave'` during initialization. Do not substitute `inactive: true` for the verified override.

Container Python diagnostics use:

```text
/usr/local/searxng/.venv/bin/python3
```

Use `docker exec -i` for heredoc/stdin diagnostics.

## 9. Standard production preflight

Before any new live or mutating production operation establish at least:

```text
exact expected HEAD
branch=main when operating production checkout
tracked worktree clean
persistent freelancer_bot runtime stopped unless explicitly authorized
canonical runtime env loaded when DB/Alembic is needed
Alembic current expected
SearXNG running on loopback 8888
Vaultwarden unchanged
required safety flags unchanged
```

Any future Web canary must additionally revalidate its exact command, profile state, fresh run key, baseline counters and effective provider health.

Provider-health semantics remain:

```text
UNAVAILABLE -> BLOCK
BACKOFF with backoff_until > now -> BLOCK
BACKOFF with backoff_until <= now -> not a blocker; effective state DEGRADED
DEGRADED -> not a blocker by itself
READY -> PASS
```

Read-only evidence never authorizes repair or a live invocation.

## 10. One-attempt authorization and run-key rules

For bounded discovery canaries:

```text
1. verify the exact run key is unused;
2. capture pre-run counters;
3. invoke the exact reviewed command once;
4. authorization is consumed when the invocation is issued;
5. do not retry under the same authorization;
6. capture persisted evidence and post-run continuity;
7. return to the orchestrator for the next decision.
```

A parse rejection is not provider evidence but still consumes authorization if invocation was the defined consumption point. A runtime failure before `discovery_runs` creation also consumes it.

Historical PR24 retired key:

```text
RETIRED_RUN_KEY=owner-profile-web-pr24-bounded-20260911-v1
RETIRED_RUN_KEY_STATUS=RETIRED_DO_NOT_REUSE
AUTHORIZED_LIVE_COMMAND_ATTEMPTS=1
LIVE_COMMAND_ATTEMPTS=2
```

The PR27 replacement key is no longer proposed/unused. It was consumed by the successful bounded canary:

```text
RUN_KEY=owner-profile-web-pr27-bounded-20260911-v1
DISCOVERY_RUN_ID=6a529712-6a7f-44a4-bd39-c8b23d25d44b
DISCOVERY_RUN_STATUS=completed
AUTHORIZATION_CONSUMED=YES
RETRY_ALLOWED=NO
```

## 11. PR27 bounded Web evidence

Exact-head production canary outcome:

```text
PR27_BOUNDED_WEB_CANARY=PASS
PRODUCTION_HEAD=f39eb215526c9ff18bd2227ccf0f3cd40304407f
LIVE_COMMAND_EXIT_CODE=0
GENERATED_QUERY_COUNT=36
EXECUTABLE_QUERY_COUNT=34
SELECTED_QUERY_COUNT=12
EXECUTED_QUERY_COUNT=12
SELECTED_DIRECT=4
SELECTED_BUYER_HABITAT=4
SELECTED_ADJACENT=4
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
```

Angle attribution proves:

```text
NON_DIRECT_LIVE_YIELD_PROVEN=YES
NON_DIRECT_ONLY_LIVE_YIELD_PROVEN=NO
NON_DIRECT_SUPPORTED_UNIQUE_CANDIDATES=3
NOVELTY_IMPROVED=NO
```

Compared with PR23, search results rose `7 -> 19` and Telegram-like matches rose `6 -> 18`, while unique candidates stayed `4 -> 4` and new candidates stayed `0 -> 0`. Do not claim buyer-habitat/adjacent improved novelty or found a new source.

## 12. Telegram collector identity and controlled cleanup

Initial PRELIVE found:

```text
ACTIVE_TELEGRAM_COLLECTOR_COUNT=2
ACTIVE_TELEGRAM_COLLECTOR_IDS=1,2
```

Exact-head code supports this state: session source listing resolves `client.get_me()` and collector-account `ensure(... active_on_create=True)` is scoped to `(platform, external_account_id)`; it does not deactivate an older row with another external ID.

Read-only evidence showed collector `2` carries the historical production activity. A separately authorized identity-only gate proved the configured Telethon session is collector `2`:

```text
CURRENT_SESSION_COLLECTOR_ACCOUNT_ID=2
CURRENT_SESSION_BINDING_PROVEN=YES
CURRENT_SESSION_MATCHES_HISTORICAL_PRODUCTION_COLLECTOR=YES
CURRENT_SESSION_IS_BOT=NO
COLLECTOR_ACCOUNT_MUTATION_PERFORMED=NO
DELTA_TELEGRAM_OPERATION_EVENTS=0
```

The initial two-active-row state above is historical evidence. After PR29 was reviewed, merged and synced to production, Owner separately authorized one explicit mutation through the verified repository API:

```text
PRODUCTION_HEAD=c89e473fdd8895aefb7a0fac3a863468d56ab56e
REPOSITORY_API=CollectorAccountRepository.set_active
UPDATED_COLLECTOR_ID=1
COLLECTOR_1_IS_ACTIVE=NO
COLLECTOR_2_IS_ACTIVE=YES
ACTIVE_TELEGRAM_COLLECTOR_COUNT=1
ACTIVE_TELEGRAM_COLLECTOR_IDS=2
COLLECTOR_1_CLEANUP_COMPLETED=YES
COLLECTOR_1_CLEANUP_RESULT=PASS
COLLECTOR_1_CLEANUP_AUTHORIZATION_CONSUMED=YES
```

Collector `1` was deactivated, not deleted. Its repository-maintained `updated_at` changed as expected; its semantic state and all dependent operation-state, operation-event, Telegram-validation, raw-message and source-access surfaces remained unchanged. Collector `2` remained unchanged and is still the previously proven current session identity / historical production collector. The cleanup made no Telegram, Web or AI request and performed no source lifecycle mutation, notification, join/leave request, service restart, runtime-env change or persistent-runtime start.

Do not infer collector `1`'s exact historical Telegram-user origin from this cleanup. The cleanup authorization is consumed and does not authorize another mutation.

## 13. Bounded Telegram source access/freshness evidence

The authorized source probe was guarded to collector `2` and issued exactly four governed source operations:

```text
BOUNDED_TELEGRAM_PROBE_EXECUTION=PASS
IDENTITY_GUARD_COLLECTOR_2_MATCH=YES
MAX_GOVERNED_SOURCE_OPERATIONS=4
GOVERNED_SOURCE_OPERATIONS_ISSUED=4
FLOODWAIT_OCCURRED=NO
PRE_TELEGRAM_OPERATION_EVENT_COUNT=203
POST_TELEGRAM_OPERATION_EVENT_COUNT=207
DELTA_TELEGRAM_OPERATION_EVENTS=4
NEW_OPERATION_EVENTS_ON_OTHER_COLLECTORS=0
```

Source results:

```text
SOURCE_19_HANDLE=@phystechcareerchannel
SOURCE_19_ENTITY_RESOLVED=YES
SOURCE_19_USERNAME_MATCH=YES
SOURCE_19_HISTORY_READ=YES
SOURCE_19_LATEST_MESSAGE_AT=2026-09-09T07:03:47+00:00
SOURCE_19_FRESH_WITHIN_10_DAYS=YES
SOURCE_19_LIFECYCLE=candidate

SOURCE_20_HANDLE=@juniors_rabota_jobs
SOURCE_20_ENTITY_RESOLVED=YES
SOURCE_20_USERNAME_MATCH=YES
SOURCE_20_HISTORY_READ=YES
SOURCE_20_LATEST_MESSAGE_AT=2026-09-11T07:08:01+00:00
SOURCE_20_FRESH_WITHIN_10_DAYS=YES
SOURCE_20_LIFECYCLE=candidate
```

The probe did **not** call the lifecycle validation service and performed no lifecycle transition, join/leave request or Owner notification itself:

```text
SOURCE_VALIDATION_SERVICE_CALLED=NO
LIFECYCLE_TRANSITIONS_PERFORMED=NO
OWNER_NOTIFICATIONS_SENT=0
JOIN_LEAVE_REQUESTS=0
SOURCE_19_20_LIFECYCLE_DECISION=NONE
```

Operationally separate these concepts:

```text
public entity resolution / history readability / freshness
!= lifecycle approval
!= Telegram membership
!= live-update readiness
!= Owner notification
!= persistent collection
```

Do not approve, join, notify, clean up collector rows, or start runtime based solely on this evidence.

## 14. Existing Owner candidate-notification evidence

A later newly authorized notification proof stopped safely in read-only PRELIVE. The target rows already existed, so no Telegram client or network send was invoked and the live checkpoint is retired:

```text
SOURCE_19_20_NOTIFICATION_PRELIVE=FAIL_PREEXISTING_DURABLE_ROWS
PRE_TARGET_OWNER_NOTIFICATION_COUNT=2
PRE_TARGET_ANY_RECIPIENT_NOTIFICATION_COUNT=2
PRE_OWNER_NOTIFICATION_COUNT=3
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

A separate read-only diagnostic proved three total Owner notification rows for source IDs `19`, `20`, and `21`. The two target rows are terminal successful deliveries to the current Owner:

```text
SOURCE_19_NOTIFICATION_ROW_ID=1
SOURCE_19_OWNER_CANDIDATE_NOTIFICATION=sent
SOURCE_19_RECIPIENT_IS_CURRENT_OWNER=YES
SOURCE_19_ATTEMPTED_AT=2026-09-08T14:27:58.543085+00:00
SOURCE_19_CREATED_AT=2026-09-08T14:27:58.543085+00:00
SOURCE_19_UPDATED_AT=2026-09-08T14:27:58.606278+00:00
SOURCE_19_SENT_AT=2026-09-08T14:27:58.606278+00:00
SOURCE_19_NOTIFICATION_LATEST_MESSAGE_AT=2026-09-04T19:01:01+00:00
SOURCE_19_TELEGRAM_MESSAGE_ID_PRESENT=YES
SOURCE_19_FAILURE_CODE=NONE
SOURCE_19_STATUS_PAYLOAD_CONSISTENT=YES
SOURCE_19_SNAPSHOT_LIFECYCLE=candidate

SOURCE_20_NOTIFICATION_ROW_ID=2
SOURCE_20_OWNER_CANDIDATE_NOTIFICATION=sent
SOURCE_20_RECIPIENT_IS_CURRENT_OWNER=YES
SOURCE_20_ATTEMPTED_AT=2026-09-08T14:28:32.725012+00:00
SOURCE_20_CREATED_AT=2026-09-08T14:28:32.725012+00:00
SOURCE_20_UPDATED_AT=2026-09-08T14:28:32.769672+00:00
SOURCE_20_SENT_AT=2026-09-08T14:28:32.769672+00:00
SOURCE_20_NOTIFICATION_LATEST_MESSAGE_AT=2026-09-08T14:15:32+00:00
SOURCE_20_TELEGRAM_MESSAGE_ID_PRESENT=YES
SOURCE_20_FAILURE_CODE=NONE
SOURCE_20_STATUS_PAYLOAD_CONSISTENT=YES
SOURCE_20_SNAPSHOT_LIFECYCLE=candidate

SOURCE_19_20_OWNER_NOTIFICATION_TO_CURRENT_OWNER=PROVEN
DURABLE_AT_MOST_ONCE_MARKERS_PRESENT=YES
REPEAT_NOTIFICATION_NEEDED=NO
REPEAT_NOTIFICATION_AUTHORIZED=NO
```

Both rows have a Telegram message ID, no failure code and internally consistent terminal payloads. Their notification-time `latest_message_at` values are historical snapshots and must not be replaced by the newer access/freshness-probe values.

The row timestamps, nearby collector-`2` `ENTITY_ACCESS`/`HISTORY` events and durable scan state are `TEMPORAL/STRUCTURAL_INFERENCE` compatible with the standard candidate-notification flow. Exact command attribution is not persisted:

```text
ROW_ORIGIN_EXACT_COMMAND_PROVABLE_FROM_SCHEMA=NO
ROW_ORIGIN_DIRECTLY_PERSISTED=NO
NOTIFICATION_ROW_COLLECTOR_FK_PRESENT=NO
NOTIFICATION_ROW_GOVERNOR_EVENT_FK_PRESENT=NO
```

The compatible but non-linked sequence was:

```text
ATTRIBUTION_CLASS=TEMPORAL/STRUCTURAL_INFERENCE
SOURCE_19_NEARBY_EVENTS=198:entity_access:completed,199:history:completed
SOURCE_20_NEARBY_EVENTS=200:entity_access:completed,201:history:completed
FOLLOWING_EVENTS=202:entity_access:completed,203:history:completed
NEARBY_EVENT_COLLECTOR_ACCOUNT_ID=2
CURRENT_OWNER_SCAN_LAST_SOURCE_ID=21
CURRENT_OWNER_SCAN_CREATED_AT=2026-09-08T14:06:21.852702+00:00
CURRENT_OWNER_SCAN_UPDATED_AT=2026-09-08T14:27:48.912712+00:00
```

Do not delete or reset the rows to force a repeat proof. A terminal `sent` row proves durable candidate-card delivery persistence, not lifecycle approval, membership, live-update readiness, Owner review, useful personalized opportunity delivery or recurring automation.

## 15. Shared-host no-touch boundary

LeadRadar tasks must not modify unrelated host workloads:

```text
WayFound
Hermes
Vaultwarden
unrelated Docker containers/networks/volumes
unrelated systemd services
firewall
system time/NTP
global Python
unrelated databases
```

Vaultwarden owns `127.0.0.1:8080`; LeadRadar SearXNG remains on `127.0.0.1:8888`.

## 16. Production promotion contract

Before syncing a reviewed change to production:

```text
1. verify current production HEAD;
2. verify tracked worktree clean;
3. fetch origin;
4. require origin/main to equal the exact authorized target;
5. verify old production head is an ancestor of the target;
6. verify reviewed PR head provenance when applicable;
7. fast-forward only;
8. verify exact HEAD after sync;
9. re-check runtime continuity;
10. keep activation/runtime restart separate unless explicitly authorized.
```

Do not use local merge, rebase, destructive reset or a newer-than-authorized target.

## 17. Current rollout and authorization state

```text
PR24_MERGED=YES
PR24_PRODUCTION_SYNCED=YES
PR24_POST_SYNC_VERIFICATION=PASS
PR24_STAGE_A_OFFLINE=PASS
PR27_REVIEWED=PASS
PR27_MERGED=YES
PR27_PRODUCTION_SYNCED=YES
PR27_POST_SYNC_VERIFICATION=PASS
PR27_TECHNICAL_PRELIVE=PASS
PR27_BOUNDED_WEB_CANARY=PASS
PR29_REVIEWED=PASS
PR29_MERGED=YES
PR29_PRODUCTION_DOCS_SYNC=PASS
PR30_REVIEWED=PASS
PR30_MERGED=YES
PR30_PRODUCTION_DOCS_SYNC=PASS
PROFILE_DISCOVERY_INTENT_VERSION=profile-discovery-intent.v2
PERSISTED_V2_COUNT=1
CURRENT_V2_CONFLICT_PRESENT=NO
NON_DIRECT_LIVE_YIELD_PROVEN=YES
NON_DIRECT_ONLY_LIVE_YIELD_PROVEN=NO
NOVELTY_IMPROVED=NO
CURRENT_TELETHON_SESSION_COLLECTOR_ACCOUNT_ID=2
CURRENT_SESSION_BINDING_PROVEN=YES
COLLECTOR_1_CLEANUP_AUTHORIZATION_CONSUMED=YES
COLLECTOR_1_CLEANUP_COMPLETED=YES
COLLECTOR_1_CLEANUP_RESULT=PASS
COLLECTOR_1_IS_ACTIVE=NO
COLLECTOR_2_IS_ACTIVE=YES
ACTIVE_TELEGRAM_COLLECTOR_COUNT=1
ACTIVE_COLLECTOR_IDS=2
SOURCE_19_BOUNDED_TELEGRAM_ACCESS_FRESHNESS=PASS
SOURCE_20_BOUNDED_TELEGRAM_ACCESS_FRESHNESS=PASS
SOURCE_19_LIFECYCLE=candidate
SOURCE_20_LIFECYCLE=candidate
SOURCE_19_OWNER_CANDIDATE_NOTIFICATION=sent
SOURCE_20_OWNER_CANDIDATE_NOTIFICATION=sent
SOURCE_19_20_OWNER_NOTIFICATION_TO_CURRENT_OWNER=PROVEN
NOTIFICATION_PROOF_AUTHORIZATION_CONSUMED=NO
NOTIFICATION_PROOF_AUTHORIZATION_RETIRED_DUE_PREEXISTING_SENT_ROWS=YES
LIVE_CHECKPOINT_2_RETIRED=YES
REPEAT_NOTIFICATION_AUTHORIZED=NO
SOURCE_19_20_JOIN_PERFORMED=NO
SOURCE_19_20_LIFECYCLE_DECISION=NONE
CANDIDATE_NOTIFICATION_RECURRING_AUTOMATION_AUTHORIZED=NO
PERSISTENT_RUNTIME_AUTHORIZED=NO
NEW_LIVE_ACTION_AUTHORIZED=NO
```

The successful bounded gates do not authorize a repeat or a new operation.

Required next ordering:

```text
1. docs reconciliation with source 19/20 notification-row evidence
2. independent review
3. Owner merge authorization
4. merge reviewed docs head
5. docs-only production sync / exact-head reconciliation as required
6. then choose the next separate Owner-authorized gate
```

The next gate has not been selected. Source lifecycle decisions, membership provisioning and persistent runtime remain separate future choices. The obsolete notification-proof checkpoint must not be retried.

## 18. Documentation precedence for operations

For production commands, use this order:

```text
1. fresh server evidence at the exact production HEAD
2. exact repository code / --help at that HEAD
3. this OPERATIONS.md
4. DEPLOYMENT.md / CURRENT_STATE.md / ACTIVE_PLAN.md
5. historical reports
```

If any canonical document disagrees with fresh exact-head evidence, STOP and reconcile documentation before designing a new live task.
