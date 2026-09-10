# LeadRadar — Production Operations

**Status:** CANONICAL  
**Last verified:** 2026-09-10  
**Production baseline:** `1299e64f28886dffe3b4bb0ddc201952aa8a2a28`

This document is the operational source of truth for the current LeadRadar production environment. It records only facts proven from the exact repository commit and the read-only production inventory. If a future code or deployment change invalidates any item below, update this document before using old commands in a new server task.

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

Persistent LeadRadar application runtime is currently not authorized and must remain stopped outside a separately authorized runtime gate.

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

`freelancer_bot/__main__.py` calls `freelancer_bot.app.cli()`. This is the application/runtime CLI.

### Operator CLI

```bash
./.venv/bin/python -m freelancer_bot.operator_cli --help
```

This is the bounded operator/maintenance CLI. Profile Web Discovery lives here.

### Verified profile Web Discovery command

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

`--max-queries` bounds only this explicit one-shot operator invocation. It does not bound or authorize the persistent runtime.

Before any live run, verify the command contract with:

```bash
./.venv/bin/python -m freelancer_bot.operator_cli \
  profile-discovery run --help
```

For one-attempt canaries, also validate the exact future argv through the parser without dispatch before Owner authorization. Parser acceptance proves only the argparse contract; profile state, run-key freshness, provider health and other operational conditions remain separate checks.

## 5. Operator CLI command catalog

The following command families exist in `freelancer_bot.operator_cli`. Presence does not imply production authorization.

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

### Authorization classes

Treat commands by side effect, not by name:

```text
READ-ONLY / OFFLINE candidates:
  --help
  collectors status
  telegram-discovery status
  telegram-discovery topics
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

The classification above is operational guidance. Before using a command in a production task, inspect its current implementation and `--help` at the exact target commit, because command behavior can change.

## 6. Database contract

LeadRadar uses SQLAlchemy async connections.

```text
Database.connect() -> sqlalchemy.ext.asyncio.AsyncConnection
read API -> connection.execute(...) / connection.scalar(...)
```

Do not assume asyncpg methods such as:

```text
fetchval
fetchrow
fetch
```

unless the exact code path explicitly returns an asyncpg connection.

Verified source lifecycle field and candidate value:

```text
sources.lifecycle_status
SourceStatus.CANDIDATE="candidate"
```

Do not use `sources.lifecycle_state`.

Verified schema symbols used for current operational counters:

```text
discovery_runs
sources
owner_source_candidate_notifications
telegram_collector_operation_events
ai_call_telemetry
source_lifecycle_events
```

Current read-only inventory at the 2026-09-10 checkpoint:

```text
DISCOVERY_RUN_COUNT=6
SOURCE_COUNT=22
CANDIDATE_COUNT=7
OWNER_NOTIFICATION_COUNT=3
TELEGRAM_OPERATION_EVENT_COUNT=203
AI_CALL_TELEMETRY_COUNT=51
SOURCE_LIFECYCLE_EVENT_COUNT=24
```

These counts are a snapshot, not invariants. Table/column names and API contracts are the durable facts.

## 7. Alembic contract

`alembic.ini` does not carry the production DSN. `migrations/env.py` first checks Alembic `sqlalchemy.url`; otherwise it resolves the database through `RuntimeConfig.from_env(mode=DATABASE)`.

Therefore production DB-connected Alembic commands require the canonical runtime env to be loaded first:

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

Never run `alembic upgrade` or `downgrade` unless a separate migration task explicitly authorizes it.

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

Do not remove those base engine definitions. Retained engine variants depend on shared network aliases, and destructive removal previously caused `KeyError: 'brave'` during SearXNG initialization.

Do not use `inactive: true` as a substitute for the verified disabled override.

Safe container inspection must use the discovered runtime interpreter when Python is required:

```text
/usr/local/searxng/.venv/bin/python3
```

For heredoc/stdin diagnostics use `docker exec -i`.

## 9. Standard read-only production preflight

A production task should normally establish these facts before any live or mutating operation:

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

For a bounded profile Web canary, PRELIVE must additionally verify:

```text
exact operator CLI --help
parser-only acceptance of the exact future argv without dispatch
profile exists, active, confirmed and at the expected revision
fresh run key absent from persisted discovery runs
baseline counters captured
effective persisted Web provider health is not blocking
```

Provider-health gating must follow the same semantics as `WebDiscoveryGovernor.restore()`:

```text
UNAVAILABLE -> BLOCK
BACKOFF with backoff_until > now -> BLOCK
BACKOFF with backoff_until <= now -> not a blocker; effective state becomes DEGRADED
DEGRADED -> not a blocker by itself
READY -> PASS
```

Read-only evidence does not authorize repair or the live invocation itself.

## 10. Run-key and one-attempt rules

For bounded discovery canaries:

```text
1. verify the exact run key does not already exist;
2. capture pre-run counters;
3. invoke the exact reviewed operator CLI command once;
4. once the invocation command is issued, the Owner authorization is consumed;
5. do not retry under the same authorization, even if failure happens before useful provider work;
6. capture persisted run evidence, post-run counters and final continuity;
7. return to the orchestrator for the next decision.
```

A CLI parse rejection is not Web/provider evidence, but it still consumes an authorization if the authorized invocation command was actually issued under a one-attempt task.

## 11. Shared-host no-touch boundary

LeadRadar tasks must not modify unrelated host workloads, including:

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

Vaultwarden is especially relevant because it owns host port `127.0.0.1:8080`; LeadRadar SearXNG is intentionally bound to `127.0.0.1:8888`.

## 12. Production promotion contract

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
10. keep activation/runtime restart as a separate authorization unless explicitly included.
```

Do not use local merge, rebase, destructive reset or a newer-than-authorized `origin/main` target.

## 13. Current rollout state

At this baseline:

```text
PR24_MERGED=YES
PR24_PRODUCTION_SYNCED=YES
PR24_POST_SYNC_VERIFICATION=PASS
PR24_STAGE_A_OFFLINE=PASS
PR24_LIVE_YIELD_IMPROVEMENT_PROVEN=NO
PR25_REVIEWED=PASS
PR25_MERGED=YES
PR25_PRODUCTION_DOCS_SYNC=DEFERRED
PERSISTENT_RUNTIME_AUTHORIZED=NO
TELEGRAM_CANDIDATE_VALIDATION_AUTHORIZED=NO
NEW_PR24_WEB_CANARY_AUTHORIZED=NO
```

PR25 is docs-only. Its production docs sync is intentionally deferred and should be combined with the next meaningful production update; no separate docs-only server sync is required now.

The first attempted PR24 live canary did not reach Web Discovery because the wrong CLI namespace was invoked. That attempt is not evidence about SearXNG/provider quality or PR24 candidate yield.

Before another live PR24 canary:

```text
1. run a separate read-only PRELIVE at the exact production HEAD;
2. verify production continuity, exact operator CLI --help and parser-only exact future argv;
3. verify profile active/confirmed/revision=8 and fresh run key absence;
4. verify effective persisted provider health using runtime backoff semantics;
5. capture baseline counters;
6. only if PRELIVE=PASS, obtain a fresh Owner authorization;
7. execute exactly one bounded Web-only invocation with the fresh run key;
8. do not retry under the same authorization;
9. compare non-direct yield and candidate novelty against the PR23 baseline;
10. only then decide whether Telegram validation is justified.
```

The separate PRELIVE task must not issue the live discovery invocation. Telegram, AI, persistent runtime, restart/recreate and repair remain outside that gate.

## 14. Documentation precedence for operations

For production commands, use this order:

```text
1. fresh server evidence at the exact production HEAD
2. exact repository code / --help at that HEAD
3. this OPERATIONS.md
4. DEPLOYMENT.md / CURRENT_STATE.md / ACTIVE_PLAN.md
5. historical reports
```

If any canonical document disagrees with fresh exact-head evidence, STOP and reconcile documentation before designing a new live task.
