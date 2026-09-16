# LeadRadar — Current Deployment

**Status:** CANONICAL  
**Snapshot date:** 2026-09-16
**Deployment code baseline:** `ab36df17334f8eff57fe475c8090a29a6ac1243c`
**Latest verified production evidence head:** `ab36df17334f8eff57fe475c8090a29a6ac1243c`

This document records the current shared-server LeadRadar layout and deployment boundaries. Exact operational commands live in [`OPERATIONS.md`](OPERATIONS.md). A docs-only repository head can be newer than the implementation baseline without changing deployed code behavior.

PR34 deployed Alembic revision `20260914_0043` and the separate
`owner_source_candidate_probe_state` table. The migration created no inferred
historical backfill. A bounded source-`18` stale cooldown validation then
recorded one current Owner/profile/intent/revision-bound `stale_or_empty` row
with a 24-hour cooldown and proved immediate selector suppression before
Telegram. No scheduler, timer, service, runtime env, lifecycle, or membership
configuration changed. PR35 then left the production checkout at
`ab36df17334f8eff57fe475c8090a29a6ac1243c` with Alembic still
`20260914_0043` and persistent runtime stopped.

PR36 added repository unit files for a future separately authorized systemd
timer and has already been merged on GitHub main at
`21842ef0fbc110babecd7c8b559c987076e795b0`
(`PR36_REVIEWED_HEAD=2044c92288733b5dcc4fc6906c08bdb7bc53873f`). It was merged
before the required independent-review and Owner merge-authorization gates were
proven. Post-merge independent technical review passed the implementation as
safe to keep on GitHub main with two medium corrections handled by PR37. The
production checkout remains `ab36df17334f8eff57fe475c8090a29a6ac1243c`; the
unit files are not installed in `/etc/systemd/system`, the timer is not enabled,
and production recurring notification automation remains unauthorized.

Current fresh evidence includes PR34 merge/sync/migration, read-only cooldown
PRELIVE, source-`18` stale cooldown validation, bounded Web replenishment
yielding current-strong candidates `23`, `24`, and `26`, stale no-send outcomes
for `23`/`24`, and one durable sent card for `26`. Source `26` remains a
candidate and its membership is unproven. Production scan cursor is `18`; total
Owner candidate notification rows remain `4`.

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
alembic_current=20260914_0043
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

## PR34 cooldown deployment and validation state

```text
PR34_REVIEWED_HEAD=656443ea9e64a3f757ef05309a502c6661841523
PR34_MERGE_COMMIT=d7f1248fdee62d6eee13e4256614ee15c4cc2846
PRODUCTION_HEAD=ab36df17334f8eff57fe475c8090a29a6ac1243c
ALEMBIC_CURRENT=20260914_0043
PERSISTENT_RUNTIME=STOPPED
COOLDOWN_BACKOFF_PRODUCTION_VALIDATED=YES
```

The deployed `owner_source_candidate_probe_state` table currently has one
proven source-`18` stale row for the active Owner/profile/intent/revision
binding:

```text
SOURCE_18_PROBE_OUTCOME=stale_or_empty
SOURCE_18_PROBE_COOLDOWN_SECONDS=86400
SOURCE_18_NOTIFICATION_ROW_COUNT=0
POST_SCAN_CURSOR=18
POST_READ_ONLY_COOLDOWN_SUPPRESSED_COUNT=1
POST_READ_ONLY_SOURCE_18_ELIGIBLE=NO
POST_READ_ONLY_ELIGIBLE_PAGE_SOURCE_IDS=23,24
OWNER_NOTIFICATION_COUNT=4
```

This proves the stale 24-hour cooldown path and immediate selector suppression.
It does not prove source `18` notification, approval, join/membership, or an
exact latest-message timestamp. It does not prove cooldown rows for sources
`23` or `24`, and it does not prove the unresolvable escalation sequence live.

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
1. implement PR37 narrow corrections
2. independent review exact PR37 head
3. explicit OWNER merge authorization for PR37
4. merge exact reviewed PR37 head
5. reconcile GitHub main to exact PR37 merge commit
6. OWNER explicitly accepts already-merged PR36 technical state plus PR37 correction
7. obtain separate production git sync authorization
8. production sync only
9. run read-only PRELIVE: verify exact unit files, ExecStart, 3-hour UTC calendar, runtime env path existence without printing contents, project Python, Alembic 20260914_0043, persistent runtime stopped, and timer not installed/enabled/active
10. obtain separate OWNER authorization to install the systemd units, run daemon-reload, and enable the timer
11. observe one real scheduled timer fire
12. verify bounded pass summary and no persistent runtime
```

Known evidence is limited to the earlier stale/empty result for source `18`,
then replenishment producing current-strong sources `23`, `24`, and `26`:
sources `23` and `24` were stale/empty no-sends, while source `26` produced one
durable sent Owner card. PR34 then recorded one source-`18` stale cooldown row,
advanced the scan cursor to `18`, and immediately suppressed source `18` before
Telegram. The current proven Owner notification count is `4`. This does not
establish the total current strong
pool. Source `26` remains lifecycle `candidate`, and its membership is not
proven.

Current authorization state:

```text
PR36_MERGED=YES
PR36_REVIEWED_HEAD=2044c92288733b5dcc4fc6906c08bdb7bc53873f
PR36_MERGE_COMMIT=21842ef0fbc110babecd7c8b559c987076e795b0
GITHUB_MAIN_HEAD=21842ef0fbc110babecd7c8b559c987076e795b0
PRODUCTION_HEAD=ab36df17334f8eff57fe475c8090a29a6ac1243c
ALEMBIC_CURRENT=20260914_0043
COOLDOWN_BACKOFF_PRODUCTION_VALIDATED=YES
RECURRING_NOTIFICATION_SCHEDULER_IMPLEMENTED=YES
RECURRING_NOTIFICATION_AUTOMATION_DEPLOYED=NO
RECURRING_NOTIFICATION_AUTOMATION_AUTHORIZED=NO
RECURRING_NOTIFICATION_TIMER_ENABLED=NO
PERSISTENT_RUNTIME_AUTHORIZED=NO
PERSISTENT_RUNTIME=STOPPED
CURRENT_GATE=PR36_POST_MERGE_CORRECTIVE_PR_REVIEW
AFTER_PR37_MERGE_NEXT_GATE=OWNER_ACCEPTANCE_OF_ALREADY_MERGED_PR36_GITHUB_STATE
PR36_POST_MERGE_TECHNICAL_REVIEW=PASS
PR36_CORRECTIVE_PR_REQUIRED=YES
PR36_PRODUCTION_SYNC_COMPLETED=NO
ORCHESTRATION_GATE_BYPASS=YES
PRE_MERGE_INDEPENDENT_REVIEW_OCCURRED=NO
PRE_MERGE_OWNER_AUTHORIZATION_PROVEN=NO
POST_MERGE_INDEPENDENT_TECHNICAL_REVIEW=PASS_WITH_2_MEDIUM_CORRECTIONS
```

PR36 defines the future recurring target as a systemd timer plus bounded
Type=oneshot service. The service invokes only:

```bash
/opt/leadradar/LeadRadar/.venv/bin/python -m freelancer_bot \
  --owner-candidate-notifications \
  --owner-candidate-notification-limit 5
```

The timer is anchored to UTC every three hours:

```text
OnCalendar=*-*-* 00/3:00:00 UTC
Persistent=false
```

It considers at most 5 candidates per pass; it does not promise exactly five
sends. It is not deployed, not enabled, and not authorized in production. Steps
6 and later in the required order are not authorized now. No installed systemd
timer, cron schedule, persistent runtime, or active 3-hour automation exists.

Keep `relevance_class=strong`; do not lower the threshold merely to produce a
card. No production sync, migration, Telegram, Web, AI, scheduler, recurring
automation, or runtime action is authorized by this documentation follow-up.

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
