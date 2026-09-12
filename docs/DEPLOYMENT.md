# LeadRadar — Current Deployment

**Status:** CANONICAL  
**Snapshot date:** 2026-09-12
**Deployment code baseline:** `81a675b72ed4c1229cedad28e5d2e1f56bac1f66`
**Latest verified production evidence head:** `b660bdd633137f13dae5a8524f14d36c0f5ecd05`

This document records the current shared-server LeadRadar layout and deployment boundaries. Exact operational commands live in [`OPERATIONS.md`](OPERATIONS.md). A docs-only repository head can be newer than the implementation baseline without changing deployed code behavior.

## Server layout

```text
checkout=/opt/leadradar/LeadRadar
runtime_env=/opt/leadradar/runtime/.env
runtime_sessions=/opt/leadradar/runtime/sessions/
venv=/opt/leadradar/LeadRadar/.venv
python=3.14.7
production_python=./.venv/bin/python
```

Do not modify shared-host global Python for LeadRadar work.

## PostgreSQL

Verified production topology:

```text
container=leadradar-postgres
image=postgres:18.4-alpine
host_bind=127.0.0.1:55432->5432/tcp
health=healthy
alembic_current=20260908_0042
```

The canonical runtime env must be loaded before DB-connected Alembic commands. Never print PostgreSQL credentials or the full credentialed `DATABASE_URL`.

## SearXNG

Verified production topology:

```text
endpoint=http://127.0.0.1:8888
container=freelancer-lead-bot-searxng-1
image_id_prefix=892cf8093419
pinned_image=searxng/searxng@sha256:892cf809341915a4b7710d3c9045005b4c377d51335a089b6d4da0b28750788d
host_bind=127.0.0.1:8888->8080/tcp
host_settings=config/searxng/settings.yml
container_settings=/etc/searxng/settings.yml
settings_mount=read-only
runtime_interpreter=/usr/local/searxng/.venv/bin/python3
state=running
```

Current verified engine strategy:

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

This preserves inherited network aliases. Do not replace it with destructive engine removal or `inactive: true`.

## Shared-host no-touch neighbor

Vaultwarden owns host port 8080:

```text
container=vaultwarden
image=vaultwarden/server:latest
host_bind=127.0.0.1:8080->80/tcp
health=healthy
```

LeadRadar SearXNG therefore remains on loopback port 8888. LeadRadar tasks must not modify Vaultwarden.

## Runtime state

There is currently no persistent LeadRadar application runtime.

Expected outside explicitly authorized bounded tasks:

```text
application_process=not running
collector=not running
bot=not running
persistent_runtime_authorized=NO
```

No persistent runtime should be started implicitly by a SearXNG, documentation, database-read, bounded Web-discovery or bounded Telegram-validation task.

## Current safety flags

Verified production values:

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

These values are production state, not `.env.example` completeness claims.

## Telegram identities, sessions and collector-account rows

Runtime session directory:

```text
/opt/leadradar/runtime/sessions/
```

Accepted identity separation remains:

```text
dedicated Telegram account -> collector
owner main Telegram account -> bot user/recipient
Telegram bot -> separate bot identity
```

A separately authorized identity-only production gate proved that the currently configured Telethon collector session resolves to:

```text
CURRENT_SESSION_COLLECTOR_ACCOUNT_ID=2
CURRENT_SESSION_BINDING_PROVEN=YES
CURRENT_SESSION_MATCHES_HISTORICAL_PRODUCTION_COLLECTOR=YES
CURRENT_SESSION_IS_BOT=NO
```

The initial identity PRELIVE observed this now-historical state:

```text
ACTIVE_TELEGRAM_COLLECTOR_COUNT=2
ACTIVE_TELEGRAM_COLLECTOR_IDS=1,2
DUPLICATE_ACTIVE_COLLECTOR_ROWS_PRESENT=YES
COLLECTOR_1_CLEANUP_COMPLETED=NO
```

After PR29 was reviewed, merged and synced to production, a separate Owner-authorized controlled cleanup used `CollectorAccountRepository.set_active` to produce the current state:

```text
PRODUCTION_HEAD=c89e473fdd8895aefb7a0fac3a863468d56ab56e
ACTIVE_TELEGRAM_COLLECTOR_COUNT=1
ACTIVE_TELEGRAM_COLLECTOR_IDS=2
COLLECTOR_1_IS_ACTIVE=NO
COLLECTOR_2_IS_ACTIVE=YES
COLLECTOR_1_CLEANUP_COMPLETED=YES
COLLECTOR_1_CLEANUP_RESULT=PASS
```

Collector `1` was deactivated, not deleted. Its exact historical Telegram-user origin remains unproven. Its operation-state row and historical dependent references remain persisted and unchanged; collector `2` was not recreated and its session did not change. Exact-head code had allowed the pre-cleanup state because collector-account `ensure()` is scoped by `(platform, external_account_id)` and does not automatically deactivate an older row for another external account.

Session files are bearer credentials. Never print or copy session contents. Two LeadRadar processes must not use the same session concurrently. The collector `1` cleanup authorization is consumed; any further collector-row mutation requires a new explicit authorization.

The owner-only bot allowlist remains part of the deployment boundary; the numeric owner Telegram ID must not be recorded in canonical docs or reports.

## Source catalog and lifecycle

Repository seed remains configuration/diagnostic input. PostgreSQL is the runtime lifecycle authority.

Verified lifecycle field:

```text
sources.lifecycle_status
candidate_value=candidate
```

Latest bounded inventory evidence includes:

```text
SOURCE_COUNT=22
CANDIDATE_COUNT=7
OWNER_NOTIFICATION_COUNT=3
TELEGRAM_OPERATION_EVENT_COUNT=207
```

Counts are snapshots, not invariants.

The PR27 Web canary materialized four existing sources. Two current candidates with non-direct support were then explicitly chosen for a separate bounded Telegram access/freshness probe:

```text
SOURCE_19_HANDLE=@phystechcareerchannel
SOURCE_19_LIFECYCLE=candidate
SOURCE_20_HANDLE=@juniors_rabota_jobs
SOURCE_20_LIFECYCLE=candidate
```

Through proven collector `2`, both sources resolved, matched their usernames, allowed public-history reads, and had a latest message within 10 days:

```text
SOURCE_19_BOUNDED_TELEGRAM_ACCESS_FRESHNESS=PASS
SOURCE_19_LATEST_MESSAGE_AT=2026-09-09T07:03:47+00:00
SOURCE_20_BOUNDED_TELEGRAM_ACCESS_FRESHNESS=PASS
SOURCE_20_LATEST_MESSAGE_AT=2026-09-11T07:08:01+00:00
```

This is **not** deployment membership evidence. Neither source was joined, approved, rejected or notified by that access/freshness gate:

```text
SOURCE_19_20_JOIN_PERFORMED=NO
SOURCE_19_20_LIFECYCLE_DECISION=NONE
OWNER_NOTIFICATIONS_SENT=0
```

Public-history readability and freshness must not be conflated with lifecycle approval, Telegram membership or live-update readiness.

Fresh read-only evidence later proved that both sources already had durable terminal Owner candidate-notification rows dated 2026-09-08:

```text
SOURCE_19_OWNER_CANDIDATE_NOTIFICATION=sent
SOURCE_20_OWNER_CANDIDATE_NOTIFICATION=sent
SOURCE_19_20_OWNER_NOTIFICATION_TO_CURRENT_OWNER=PROVEN
DURABLE_AT_MOST_ONCE_MARKERS_PRESENT=YES
REPEAT_NOTIFICATION_NEEDED=NO
REPEAT_NOTIFICATION_AUTHORIZED=NO
```

A newly authorized notification-proof PRELIVE stopped before Telegram when it found those rows. The authorization was not consumed by a network attempt, but the old live checkpoint is retired because the product fact is already proven:

```text
SOURCE_19_20_NOTIFICATION_PRELIVE=FAIL_PREEXISTING_DURABLE_ROWS
TELEGRAM_NETWORK_ATTEMPTED=NO
NOTIFICATION_PROOF_AUTHORIZATION_CONSUMED=NO
LIVE_CHECKPOINT_2_EXECUTED=NO
LIVE_CHECKPOINT_2_RETIRED=YES
```

The notification rows do not persist an exact creating command, collector FK or governor-event FK. Nearby collector-`2` events, scan state and timestamps are labeled `TEMPORAL/STRUCTURAL_INFERENCE`, not direct attribution. Both sources remain `candidate`; notification does not prove lifecycle approval, membership, live-update readiness, Owner review, personalized opportunity delivery or recurring automation.

## Current PR27 live-evidence state

The PR27 bounded Web canary has now completed successfully:

```text
PR27_BOUNDED_WEB_CANARY=PASS
RUN_KEY=owner-profile-web-pr27-bounded-20260911-v1
DISCOVERY_RUN_ID=6a529712-6a7f-44a4-bd39-c8b23d25d44b
PROFILE_DISCOVERY_INTENT_VERSION=profile-discovery-intent.v2
PERSISTED_V2_COUNT=1
CURRENT_V2_CONFLICT_PRESENT=NO
NON_DIRECT_LIVE_YIELD_PROVEN=YES
NON_DIRECT_ONLY_LIVE_YIELD_PROVEN=NO
NOVELTY_IMPROVED=NO
```

The canary considered 19 search results and 18 Telegram-like matches, but yielded the same four unique known candidates as the PR23 comparison baseline and no new candidates. Buyer-habitat/adjacent contributed real live support to 3/4 candidates; no non-direct-only candidate was proven.

The one-attempt Web authorization is consumed and does not permit a retry. The later identity-only and source-probe Telegram authorizations are also consumed. No new live or mutating production action is currently authorized.

## Promotion rules

Before production checkout changes:

1. verify exact current HEAD;
2. verify tracked worktree clean;
3. fetch exact authorized target;
4. verify provenance and diff;
5. require fast-forward only;
6. verify exact HEAD after sync;
7. preserve `/opt/leadradar/runtime`;
8. keep activation/restart as a separate authorization unless explicitly included.

Do not sync to a newer-than-authorized `origin/main` and do not use local merge/rebase/destructive reset.

## Next deployment-related gate

Current required order is:

```text
1. docs reconciliation with source 19/20 notification-row evidence
2. independent review
3. Owner merge authorization
4. merge reviewed docs head
5. docs-only production sync / exact-head reconciliation as required
6. choose the next separate Owner-authorized gate
```

Source `19`/`20` lifecycle decisions, membership provisioning, recurring candidate-notification automation and persistent runtime are not authorized by this reconciliation. The pre-existing notification rows require no repeat send, and the retired live checkpoint must not be executed.

## Shared-server boundary

LeadRadar tasks must not modify:

- WayFound;
- Hermes;
- Vaultwarden;
- unrelated Docker containers, networks or volumes;
- unrelated systemd services;
- firewall;
- system time/NTP;
- global Python;
- unrelated databases.

## Secrets/reporting rules

Safe reports may include commit SHAs, migration revisions, counts, booleans, public container names, non-secret hashes and public source handles.

Reports must not contain bot tokens, API hashes, DB credentials/full DSNs, owner numeric Telegram ID, session contents, Telegram login/2FA codes, live message bodies or AI provider keys.
