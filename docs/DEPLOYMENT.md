# LeadRadar — Current Deployment

**Status:** CANONICAL  
**Snapshot date:** 2026-09-14
**Deployment code baseline:** `437c9dcc4b35846b6ce828258272814e06a79d13`
**Latest verified production evidence head:** `437c9dcc4b35846b6ce828258272814e06a79d13`

This document records the current shared-server LeadRadar layout and deployment boundaries. Exact operational commands live in [`OPERATIONS.md`](OPERATIONS.md). A docs-only repository head can be newer than the implementation baseline without changing deployed code behavior.

The cooldown/backoff PR adds Alembic revision `20260914_0043` and a separate
`owner_source_candidate_probe_state` table. It has not been deployed: production
remains at `20260908_0042`. The migration creates an empty table with no inferred
historical backfill. No scheduler, timer, service, runtime env, lifecycle, or
membership configuration changes in this PR.

Current fresh evidence includes a passed PR33 docs sync, bounded Web
replenishment yielding current-strong candidates `23`, `24`, and `26`, stale
no-send outcomes for `23`/`24`, and one durable sent card for `26`. Source `26`
remains a candidate and its membership is unproven. Production scan cursor is
`26`; total Owner candidate notification rows are `4`.

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

Historical bounded inventory evidence from the pre-replenishment checkpoint
included:

```text
SOURCE_COUNT=22
CANDIDATE_COUNT=7
OWNER_NOTIFICATION_COUNT=3
TELEGRAM_OPERATION_EVENT_COUNT=209
```

These values belong only to that older checkpoint. Counts are snapshots, not
invariants; in particular, the current proven `OWNER_NOTIFICATION_COUNT=4`
supersedes the historical value above. No newer total `SOURCE_COUNT`,
`CANDIDATE_COUNT`, or Telegram operation-event count is claimed without fresh
measurement.

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

The one-attempt Web authorization is consumed and does not permit a retry. The
later identity-only and source-probe Telegram authorizations were also consumed.
At that evidence checkpoint, no new live or mutating action was authorized.

## PR32 deployment and notification-canary state

```text
PR32_REVIEWED_HEAD=e197a532ace1a79ac5c335b5ab220ee228eda637
PR32_MERGE_COMMIT=a232cf564a57f8761af7394ea4e5607fd8b8ac6d
PR32_REVIEW=PASS
PR32_PRODUCTION_SYNC=PASS
PR32_PRODUCTION_POSTVERIFY=PASS
HIGH_RELEVANCE_GATE_SYNCED_TO_PRODUCTION=YES
CHECKPOINT_3=FAIL_INCOMPLETE
BLOCKER_CLASS=VERIFICATION_GATE_DEFECT
CHECKPOINT_3A=PASS
EFFECTIVE_SEND_CATCH_UP=false
RUNTIME_ENV_MODIFIED=NO
```

One bounded authorized notification invocation selected source `18` through
the exact current profile/intent `strong` gate and completed governed
entity/history access. It terminated without delivery because the source was
stale or had no usable latest-message timestamp:

```text
CANARY_RESULT=NO_SEND_STALE_OR_EMPTY
CANDIDATES_CONSIDERED=1
ACTIVITY_PROBES=1
STALE_OR_EMPTY=1
UNRESOLVABLE=0
RESERVED=0
SENT=0
DELTA_OWNER_NOTIFICATION_COUNT=0
POST_TARGET_NOTIFICATION_ROW_COUNT=0
POST_SCAN_CURSOR=18
DELTA_COLLECTOR_2_OPERATION_EVENT_COUNT=2
DELTA_SOURCE_LIFECYCLE_EVENT_COUNT=0
POST_SOURCE_18_LIFECYCLE=candidate
AUTHORIZATION_CONSUMED=YES
RETRY_ALLOWED=NO
HIGH_RELEVANCE_GATE_LIVE_VALIDATED=NO
READY_FOR_RECURRING_NOTIFICATION_DECISION=NO
FINAL_PERSISTENT_RUNTIME=STOPPED
```

No exact latest-message timestamp is proven. No Owner card, reservation,
lifecycle change, join/leave action, runtime-env edit, or persistent runtime
occurred. Historical source `19`/`20` sent rows predate the strong-only selector.

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
1. independent re-review of the exact follow-up head
2. OWNER merge authorization
3. merge the exact reviewed head
4. separate OWNER-authorized production sync of the exact merge result
5. apply and verify Alembic 20260914_0043 within that authorized sync/migration gate
6. read-only PRELIVE: exact synced head, migration, current binding, cooldown baseline
7. separately authorize one bounded stale/unresolvable probe to create probe state
8. prove read-only that an immediate selector suppresses that binding before Telegram
9. only after validation, discuss recurring 3h/max5 scheduling separately
```

Known evidence is limited to the earlier stale/empty result for source `18`,
then replenishment producing current-strong sources `23`, `24`, and `26`:
sources `23` and `24` were stale/empty no-sends, while source `26` produced one
durable sent Owner card. The scan cursor is `26` and the current proven Owner
notification count is `4`. This does not establish the total current strong
pool. Source `26` remains lifecycle `candidate`, and its membership is not
proven.

Implementation and test success are not production validation:

```text
COOLDOWN_BACKOFF_PRODUCTION_VALIDATED=NO
RECURRING_NOTIFICATION_AUTOMATION_AUTHORIZED=NO
PERSISTENT_RUNTIME_AUTHORIZED=NO
```

Keep `relevance_class=strong`; do not lower the threshold merely to produce a
card. No production sync, migration, Telegram, Web, AI, scheduler, or runtime
action is authorized by this documentation follow-up.

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
