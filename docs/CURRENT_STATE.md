# LeadRadar — Current State

**Status:** CANONICAL  
**Snapshot date:** 2026-09-14
**Implementation baseline:** cooldown/backoff PR based on `437c9dcc4b35846b6ce828258272814e06a79d13`
**Latest verified production evidence head:** `437c9dcc4b35846b6ce828258272814e06a79d13`

## Executive status

PR33 production docs sync passed. A later bounded profile Web replenishment
completed and added current-strong candidate sources `23`, `24`, and `26`.
Notification canaries classified sources `23` and `24` as stale/empty without
notification rows; source `26` sent one durable Owner card. Source `26` remains
`candidate`, and neither lifecycle approval nor Telegram membership is proven.

This PR implements durable exact-binding re-probe suppression in new Alembic
revision `20260914_0043`. It does not change production, whose database remains
at `20260908_0042`. Recurring notification automation and persistent runtime
remain unauthorized.

```text
PR33_PRODUCTION_DOCS_SYNC=PASS
PRODUCTION_HEAD=437c9dcc4b35846b6ce828258272814e06a79d13
BOUNDED_PROFILE_WEB_REPLENISHMENT=PASS_NEW_STRONG
REPLENISHMENT_RUN_KEY=owner-profile-web-replenishment-20260914-v1
REPLENISHMENT_DISCOVERY_RUN_ID=0d7ff4de-1845-418e-8b1b-3b78d8ae0b06
REPLENISHMENT_DISCOVERY_RUN_STATUS=completed
NEW_CURRENT_STRONG_CANDIDATE_SOURCE_IDS=23,24,26
SOURCE_23_HANDLE=backend_job_geeklink
SOURCE_24_HANDLE=well_paid_job
SOURCE_26_HANDLE=devkz_jobs
SOURCE_23_NOTIFICATION_CANARY=NO_SEND_STALE_OR_EMPTY
SOURCE_24_NOTIFICATION_CANARY=NO_SEND_STALE_OR_EMPTY
SOURCE_26_NOTIFICATION_CANARY=PASS_SENT
SOURCE_18_NOTIFICATION_ROW_COUNT=0
SOURCE_23_NOTIFICATION_ROW_COUNT=0
SOURCE_24_NOTIFICATION_ROW_COUNT=0
SOURCE_26_NOTIFICATION_STATUS=sent
POST_SCAN_CURSOR=26
OWNER_NOTIFICATION_COUNT=4
HIGH_RELEVANCE_GATE_LIVE_VALIDATED=YES
OWNER_CARD_SEND_UNDER_PR32_PROVEN=YES
SOURCE_26_LIFECYCLE=candidate
SOURCE_26_MEMBERSHIP_PROVEN=NO
COOLDOWN_BACKOFF_IMPLEMENTED=YES
COOLDOWN_BACKOFF_PRODUCTION_VALIDATED=NO
RECURRING_NOTIFICATION_AUTOMATION_AUTHORIZED=NO
PERSISTENT_RUNTIME_AUTHORIZED=NO
```

LeadRadar production is stable at merge commit `437c9dcc4b35846b6ce828258272814e06a79d13`. PR32 reviewed head `e197a532ace1a79ac5c335b5ab220ee228eda637` passed independent review, was merged and synced, and its post-sync verification passed after the initial incomplete checkpoint was corrected by checkpoint `3A`. PR33 then reconciled the canonical production evidence. The strong-only Owner candidate-notification selector is deployed; persistent runtime remains stopped.

PR24 production sync, post-sync verification and full bounded offline Stage A all passed. PR27 production sync, post-sync verification and the technical read-only PRELIVE for the repaired profile-discovery path also passed.

The subsequently authorized one-attempt PR27 bounded Web canary completed successfully on exact production head `f39eb215526c9ff18bd2227ccf0f3cd40304407f`. It persisted the current v2 intent without conflict and completed 12/12 selected queries. It increased raw search/Telegram-like support versus PR23 but did **not** improve unique-candidate novelty: all four discovered candidates were already known.

Angle attribution from persisted evidence proves that `buyer_habitat` / `adjacent` contributed live support to 3 of the 4 unique candidates. It does **not** prove a non-direct-only candidate and does **not** prove novelty improvement.

A separately authorized Telegram identity-only gate proved that the currently configured Telethon collector session maps to `collector_accounts.id=2`, which also matches the historical production collector. After PR29 was reviewed, merged and synced to production, a separate Owner-authorized controlled cleanup used `CollectorAccountRepository.set_active` to deactivate collector `1`. Collector `2` is now the sole active Telegram collector. Collector `1` was not deleted: it remains persisted for historical/FK continuity, and its operation state, events, validations, raw messages and source-access references were preserved.

A later bounded Telegram source probe, explicitly guarded to collector `2`, proved public entity resolution, public-history readability and freshness for candidate sources `19` (`@phystechcareerchannel`) and `20` (`@juniors_rabota_jobs`). Both remain lifecycle `candidate`. That probe itself sent no notification and its access/freshness evidence is not lifecycle approval, Telegram membership proof, live-update readiness or authorization for persistent collection.

A newly authorized Owner-notification proof then stopped safely in PRELIVE before Telegram because sources `19` and `20` already had durable terminal `sent` rows addressed to the current Owner. A separate read-only diagnostic proved those pre-existing rows and their internally consistent sent payloads. The exact creating command is not persisted; nearby collector-`2` governor events, scan state and timestamps are only `TEMPORAL/STRUCTURAL_INFERENCE`. No repeat notification is needed or authorized.

Persistent LeadRadar runtime remains unauthorized.

One separately authorized PR32 notification canary then selected exact current-
strong candidate source `18` and completed governed entity/history requests.
The freshness check returned `STALE_OR_EMPTY=1`, so no row was reserved and no
Owner card was sent. This proves live selector reach and freshness suppression,
not reservation, bot send, or end-to-end high-relevance notification success.
The authorization is consumed and retry is forbidden. Historical source
`19`/`20` sent rows predate this selector and remain unchanged.

## Production contract

```text
LATEST_VERIFIED_PRODUCTION_EVIDENCE_HEAD=437c9dcc4b35846b6ce828258272814e06a79d13
PRODUCTION_HEAD=437c9dcc4b35846b6ce828258272814e06a79d13
IMPLEMENTATION_BASE=437c9dcc4b35846b6ce828258272814e06a79d13
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

Latest bounded evidence snapshot:

```text
DISCOVERY_RUN_COUNT=7
SOURCE_COUNT=22
CANDIDATE_COUNT=7
OWNER_NOTIFICATION_COUNT=3
TELEGRAM_OPERATION_EVENT_COUNT=209
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

This remains the comparison baseline for PR27 bounded Web evidence.

## Historical PR24 live attempts

```text
PR24_MERGED=YES
PR24_REVIEWED_HEAD=6280c569516fdd586dd467ec2c507b816bbde844
PR24_MERGE_COMMIT=1299e64f28886dffe3b4bb0ddc201952aa8a2a28
PR24_PRODUCTION_SYNC=PASS
PR24_POST_SYNC_VERIFICATION=PASS
PR24_FULL_STAGE_A_OFFLINE=PASS
PR24_WEB_CANARY_READ_ONLY_PRELIVE=PASS
```

The first attempted live command used the wrong application CLI namespace and was rejected by parsing before Web work. Because the invocation itself was issued under a one-attempt authorization, that authorization was consumed.

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

Root-cause evidence showed only `generated_web_queries` differed under the old deterministic v1 identity. Historical v1 rows remain immutable. The old run key is retired operationally:

```text
RETIRED_RUN_KEY=owner-profile-web-pr24-bounded-20260911-v1
RETIRED_RUN_KEY_STATUS=RETIRED_DO_NOT_REUSE
```

## PR27 intent repair and bounded Web canary

PR27 repaired the root cause by versioning the immutable Profile Discovery Intent contract to `profile-discovery-intent.v2`. The earlier read-only technical PRELIVE correctly observed no persisted v2 row yet:

```text
CURRENT_INTENT_ID=b3f53d57-afd9-55e1-b822-77d687fe466d
HISTORICAL_V1_INTENT_ID=503e6238-1896-5d4a-84b1-004487d56c97
CURRENT_V2_DISTINCT_FROM_V1=YES
PERSISTED_V2_COUNT=0
CURRENT_V2_CONFLICT_PRESENT=NO
```

That PRELIVE fact is historical. The later authorized live canary persisted the v2 row and completed successfully:

```text
PR27_BOUNDED_WEB_CANARY=PASS
PRODUCTION_HEAD=f39eb215526c9ff18bd2227ccf0f3cd40304407f
RUN_KEY=owner-profile-web-pr27-bounded-20260911-v1
DISCOVERY_RUN_ID=6a529712-6a7f-44a4-bd39-c8b23d25d44b
LIVE_COMMAND_EXIT_CODE=0
DISCOVERY_RUN_STATUS=completed
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
AUTHORIZATION_CONSUMED=YES
RETRY_ALLOWED=NO
```

Product interpretation:

```text
PR27_WEB_CANARY=PASS
PR27_V2_INTENT_PERSISTENCE=PASS
LIVE_WEB_EXECUTION=PASS
NOVELTY_IMPROVED=NO
NEW_CANDIDATES=0
```

Persisted angle attribution:

```text
DIRECT_QUERY_ATTEMPTS=4
DIRECT_RAW_SEARCH_RESULTS=7
BUYER_HABITAT_QUERY_ATTEMPTS=4
BUYER_HABITAT_RAW_SEARCH_RESULTS=6
ADJACENT_QUERY_ATTEMPTS=4
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

Compared with PR23, PR27 considered 12 more search results and 12 more Telegram-like matches, but unique candidates remained 4 and new candidates remained 0. Do not claim search-quality or novelty improvement beyond the proven support attribution.

## Current Web-canary source evidence

The four materialized results were existing sources:

```text
SOURCE_ID=16 HANDLE=@job_python LIFECYCLE=approved SUPPORT=mixed_direct_and_non_direct RELEVANCE=weak SCORE=0.11000
SOURCE_ID=18 HANDLE=@ru_pythonjobs LIFECYCLE=candidate SUPPORT=direct_only RELEVANCE=strong SCORE=0.85000
SOURCE_ID=19 HANDLE=@phystechcareerchannel LIFECYCLE=candidate SUPPORT=mixed_direct_and_non_direct RELEVANCE=weak SCORE=0.07000
SOURCE_ID=20 HANDLE=@juniors_rabota_jobs LIFECYCLE=candidate SUPPORT=mixed_direct_and_non_direct RELEVANCE=weak SCORE=0.07000
```

Sources `19` and `20` were selected only as bounded Telegram access/freshness probe targets because they were current candidates with non-direct support. No lifecycle decision was made for either source.

## Collector identity and controlled cleanup state

Initial Telegram PRELIVE found:

```text
ACTIVE_TELEGRAM_COLLECTOR_COUNT=2
ACTIVE_TELEGRAM_COLLECTOR_IDS=1,2
DUPLICATE_ACTIVE_COLLECTOR_ROWS_PRESENT=YES
```

Read-only diagnosis showed collector `1` had no operation events, validations or raw messages and only its operation-state FK footprint, while collector `2` carried the historical production activity. Exact-head code supports multiple active rows because `ApprovedTelegramSourceAdapter.list_for_session()` resolves `client.get_me()` and `CollectorAccountRepository.ensure(... active_on_create=True)` is scoped to `(platform, external_account_id)` without deactivating rows for other external IDs.

A separately authorized identity-only gate then proved:

```text
CURRENT_SESSION_COLLECTOR_ACCOUNT_ID=2
CURRENT_SESSION_BINDING_PROVEN=YES
CURRENT_SESSION_MATCHES_HISTORICAL_PRODUCTION_COLLECTOR=YES
CURRENT_SESSION_IS_BOT=NO
IDENTITY_ONLY_TELEGRAM_GATE=PASS
COLLECTOR_ACCOUNT_MUTATION_PERFORMED=NO
DELTA_TELEGRAM_OPERATION_EVENTS=0
COLLECTOR_1_CLEANUP_COMPLETED=NO
```

The `COLLECTOR_1_CLEANUP_COMPLETED=NO` line above is historical identity-gate evidence. After PR29 production sync, Owner separately authorized one controlled cleanup. Pre-mutation evidence confirmed collector IDs `1` and `2` were active and collector `1` had no operation events, validations, raw messages or source-access references, while its one operation-state row remained present.

The cleanup completed through the exact repository API without Telegram or other external work:

```text
PRODUCTION_HEAD=c89e473fdd8895aefb7a0fac3a863468d56ab56e
REPOSITORY_API=CollectorAccountRepository.set_active
UPDATED_COLLECTOR_ID=1
COLLECTOR_1_PRE_IS_ACTIVE=YES
COLLECTOR_1_IS_ACTIVE=NO
COLLECTOR_2_IS_ACTIVE=YES
ACTIVE_TELEGRAM_COLLECTOR_COUNT=1
ACTIVE_TELEGRAM_COLLECTOR_IDS=2
COLLECTOR_1_CLEANUP_COMPLETED=YES
COLLECTOR_1_CLEANUP_RESULT=PASS
DATABASE_TRANSACTION_COMMITTED=YES
```

Only collector `1`'s `is_active` and repository-maintained `updated_at` changed. Collector `2` and all five dependent-state surfaces for both collectors remained unchanged by SHA-256 comparison:

```text
OPERATION_STATE_UNCHANGED=YES
OPERATION_EVENTS_UNCHANGED=YES
TELEGRAM_VALIDATIONS_UNCHANGED=YES
RAW_MESSAGES_UNCHANGED=YES
SOURCE_COLLECTOR_ACCESS_UNCHANGED=YES
TELEGRAM_REQUESTS_PERFORMED=NO
WEB_REQUESTS_PERFORMED=NO
AI_REQUESTS_PERFORMED=NO
SERVICE_RESTARTS_PERFORMED=NO
PERSISTENT_RUNTIME_STARTED=NO
```

Collector `1` was deactivated, not deleted. Its exact historical Telegram-user origin remains unproven. The cleanup did not issue a new Telegram `get_me()`; current collector `2` session binding remains supported by the earlier identity evidence.

## Bounded Telegram source access/freshness evidence

The separately authorized probe was guarded to collector `2` and issued exactly four governed source operations:

```text
BOUNDED_TELEGRAM_PROBE_EXECUTION=PASS
LIVE_PROBE_EXIT_CODE=0
IDENTITY_GUARD_COLLECTOR_2_MATCH=YES
IDENTITY_GUARD_RESULT=PASS
MAX_GOVERNED_SOURCE_OPERATIONS=4
GOVERNED_SOURCE_OPERATIONS_ISSUED=4
FLOODWAIT_OCCURRED=NO
PRE_TELEGRAM_OPERATION_EVENT_COUNT=203
POST_TELEGRAM_OPERATION_EVENT_COUNT=207
DELTA_TELEGRAM_OPERATION_EVENTS=4
NEW_OPERATION_EVENTS_ON_OTHER_COLLECTORS=0
```

Per-source results:

```text
SOURCE_19_HANDLE=@phystechcareerchannel
SOURCE_19_ENTITY_RESOLVED=YES
SOURCE_19_USERNAME_MATCH=YES
SOURCE_19_HISTORY_READ=YES
SOURCE_19_LATEST_MESSAGE_AT=2026-09-09T07:03:47+00:00
SOURCE_19_AGE_DAYS=2
SOURCE_19_FRESH_WITHIN_10_DAYS=YES
SOURCE_19_ERROR_CLASS=NONE

SOURCE_20_HANDLE=@juniors_rabota_jobs
SOURCE_20_ENTITY_RESOLVED=YES
SOURCE_20_USERNAME_MATCH=YES
SOURCE_20_HISTORY_READ=YES
SOURCE_20_LATEST_MESSAGE_AT=2026-09-11T07:08:01+00:00
SOURCE_20_AGE_DAYS=0
SOURCE_20_FRESH_WITHIN_10_DAYS=YES
SOURCE_20_ERROR_CLASS=NONE
```

That specific access/freshness probe made no notification or business-state mutation:

```text
SOURCE_19_LIFECYCLE=candidate
SOURCE_20_LIFECYCLE=candidate
OWNER_NOTIFICATIONS_SENT=0
SOURCE_19_20_JOIN_PERFORMED=NO
SOURCE_19_20_LIFECYCLE_DECISION=NONE
SOURCE_VALIDATION_SERVICE_CALLED=NO
LIFECYCLE_TRANSITIONS_PERFORMED=NO
```

Public-history readability is **not** proof of Telegram membership or live-update readiness.

## Existing Owner candidate-notification evidence

The later notification-proof PRELIVE expected no target rows, found two terminal target rows, and stopped before constructing a Telegram client or issuing a send:

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

A separate read-only diagnostic proved the current product state:

```text
DATABASE_WRITES_PERFORMED=NO
TELEGRAM_CLIENT_CONSTRUCTED=NO
TELEGRAM_NETWORK_ATTEMPTED=NO
BOT_SEND_ATTEMPTS=0
OWNER_NOTIFICATIONS_SENT_BY_DIAGNOSTIC=0
SOURCE_LIFECYCLE_MUTATIONS=0
JOIN_LEAVE_REQUESTS=0
WEB_REQUESTS_PERFORMED=0
AI_REQUESTS_PERFORMED=0
PERSISTENT_RUNTIME_STARTED=NO

SOURCE_19_20_EXISTING_NOTIFICATION_ROWS_DIAGNOSTIC=PASS
DATABASE_WRITES_PERFORMED=NO
TELEGRAM_CLIENT_CONSTRUCTED=NO
TELEGRAM_NETWORK_ATTEMPTED=NO
BOT_SEND_ATTEMPTS=0
OWNER_NOTIFICATIONS_SENT_BY_DIAGNOSTIC=0
SOURCE_LIFECYCLE_MUTATIONS=0
JOIN_LEAVE_REQUESTS=0
WEB_REQUESTS_PERFORMED=0
AI_REQUESTS_PERFORMED=0
PERSISTENT_RUNTIME_STARTED=NO
ALL_OWNER_NOTIFICATION_ROW_COUNT=3
ALL_OWNER_NOTIFICATION_SOURCE_IDS=19,20,21

SOURCE_19_OWNER_CANDIDATE_NOTIFICATION=sent
SOURCE_19_NOTIFICATION_ROW_ID=1
SOURCE_19_RECIPIENT_IS_CURRENT_OWNER=YES
SOURCE_19_SENT_AT=2026-09-08T14:27:58.606278+00:00
SOURCE_19_NOTIFICATION_LATEST_MESSAGE_AT=2026-09-04T19:01:01+00:00

SOURCE_20_OWNER_CANDIDATE_NOTIFICATION=sent
SOURCE_20_NOTIFICATION_ROW_ID=2
SOURCE_20_RECIPIENT_IS_CURRENT_OWNER=YES
SOURCE_20_SENT_AT=2026-09-08T14:28:32.769672+00:00
SOURCE_20_NOTIFICATION_LATEST_MESSAGE_AT=2026-09-08T14:15:32+00:00

SOURCE_19_20_OWNER_NOTIFICATION_TO_CURRENT_OWNER=PROVEN
DURABLE_AT_MOST_ONCE_MARKERS_PRESENT=YES
REPEAT_NOTIFICATION_NEEDED=NO
REPEAT_NOTIFICATION_AUTHORIZED=NO
ROW_ORIGIN_EXACT_COMMAND_PROVABLE_FROM_SCHEMA=NO
ROW_ORIGIN_DIRECTLY_PERSISTED=NO
ATTRIBUTION_CLASS=TEMPORAL/STRUCTURAL_INFERENCE
```

Both row payloads are consistent with terminal `sent` status, contain a Telegram message ID, and have no failure code. Their historical `latest_message_at` snapshots must remain distinct from the newer timestamps established by the later access/freshness probe. The row timestamps, collector-`2` `ENTITY_ACCESS`/`HISTORY` event sequence and durable scan state are strongly compatible with the standard candidate-notification flow, but no notification row has a persisted collector or governor-event FK and no exact creating CLI command is proven.

Notification delivery did not approve either source, prove membership/live-update readiness, or prove that the Owner reviewed the cards. It also does not prove useful end-to-end personalized opportunity delivery or recurring notification automation.

## PR32 production sync and bounded notification canary

```text
PR_NUMBER=32
REVIEWED_HEAD=e197a532ace1a79ac5c335b5ab220ee228eda637
MERGE_COMMIT=a232cf564a57f8761af7394ea4e5607fd8b8ac6d
REVIEW=PASS
PRODUCTION_SYNC=PASS
PRODUCTION_POSTVERIFY=PASS
HIGH_RELEVANCE_GATE_SYNCED_TO_PRODUCTION=YES
CHECKPOINT_3=FAIL_INCOMPLETE
CHECKPOINT_3_BLOCKER_CLASS=VERIFICATION_GATE_DEFECT
CHECKPOINT_3A=PASS
EFFECTIVE_SEND_CATCH_UP=false
```

The runtime `.env` was not modified. PRELIVE resolved profile
`e3f2a0d1-3a46-4506-8a79-f4ed47400279` revision `8` and deterministic intent
`b3f53d57-afd9-55e1-b822-77d687fe466d`. With scan cursor `21`, the exact
current-strong unnotified pool contained one source and required read-only
wrap; the next page selected source `18` (`@ru_pythonjobs`), a safe Telegram
candidate with no prior Owner notification row. Collector `2` was ready.

```text
PRE_SCAN_CURSOR=21
CURRENT_STRONG_UNNOTIFIED_POOL_COUNT=1
READ_ONLY_CURSOR_WRAP_REQUIRED=YES
READ_ONLY_NEXT_PAGE_COUNT=1
NEXT_CANDIDATE_SOURCE_ID=18
NEXT_CANDIDATE_HANDLE=@ru_pythonjobs
NEXT_CANDIDATE_LIFECYCLE=candidate
NEXT_CANDIDATE_PLATFORM=telegram
NEXT_CANDIDATE_SAFE_TELEGRAM_ADDRESS=YES
NEXT_CANDIDATE_PRE_OWNER_NOTIFICATION_COUNT=0
ACTIVE_TELEGRAM_COLLECTOR_IDS=2
COLLECTOR_OPERATION_STATUS=ready
PRE_OWNER_NOTIFICATION_COUNT=3
PRE_COLLECTOR_2_OPERATION_EVENT_COUNT=207
PRE_SOURCE_LIFECYCLE_EVENT_COUNT=24
PRELIVE_GATE=PASS
LIVE_AUTHORIZATION_CONSUMED=NO
```

One authorized invocation completed with exit code `0`:

```text
PROFILE_GATE_READY=YES
PROFILE_ID=e3f2a0d1-3a46-4506-8a79-f4ed47400279
PROFILE_REVISION=8
DISCOVERY_INTENT_ID=b3f53d57-afd9-55e1-b822-77d687fe466d
RELEVANCE_GATE=strong
CANDIDATES_CONSIDERED=1
ACTIVITY_PROBES=1
FRESH_WITHIN_10_DAYS=0
STALE_OR_EMPTY=1
UNRESOLVABLE=0
ALREADY_NOTIFIED=0
RESERVED=0
SENT=0
FAILED=0
NO_LONGER_CANDIDATE=0
IDENTITY_CHANGED=0
SOURCE_NOT_FOUND=0
POST_SCAN_CURSOR=18
DELTA_OWNER_NOTIFICATION_COUNT=0
POST_TARGET_NOTIFICATION_ROW_COUNT=0
DELTA_COLLECTOR_2_OPERATION_EVENT_COUNT=2
NEW_COLLECTOR_2_OPERATION_CATEGORIES=entity_access,history
NEW_COLLECTOR_2_OPERATION_OUTCOMES=completed,completed
FLOODWAIT_OCCURRED=NO
DELTA_SOURCE_LIFECYCLE_EVENT_COUNT=0
POST_SOURCE_18_LIFECYCLE=candidate
POST_SOURCE_18_HANDLE=@ru_pythonjobs
FINAL_PERSISTENT_RUNTIME=STOPPED
FINAL_CONTINUITY_GATE=PASS
CANARY_RESULT=NO_SEND_STALE_OR_EMPTY
HIGH_RELEVANCE_GATE_LIVE_VALIDATED=NO
STRONG_SELECTOR_LIVE_REACH_PROVEN=YES
OWNER_CARD_SEND_UNDER_PR32_PROVEN=NO
READY_FOR_RECURRING_NOTIFICATION_DECISION=NO
AUTHORIZATION_CONSUMED=YES
RETRY_ALLOWED=NO
LIVE_INVOCATION_COUNT=1
LIVE_COMMAND_EXIT_CODE=0
```

The service did not expose an exact latest-message timestamp. The supported
interpretation is only that source `18` failed the 10-day freshness requirement
because the probe yielded either no usable timestamp or activity older than the
window. Completed entity/history operations plus `UNRESOLVABLE=0` exclude an
entity-resolution failure. Reservation, `mark_sent`, bot delivery and full
end-to-end notification remain unproven under PR32.

Evidence provenance is separate from the live result block:

```text
FILTER_BEFORE_TELEGRAM_CONTRACT_PROVEN_BY=CODE_TESTS_PRELIVE
LIVE_CANARY_NEGATIVE_CONTROL_PERFORMED=NO
```

PR32 code, tests, and PRELIVE exact-selector inspection prove that non-strong or
missing-current-relevance candidates are excluded before Telegram. The live
canary selected one strong candidate and did not run a weak, adequate, or
missing-current-relevance negative control.

At production head `437c9dcc4b35846b6ce828258272814e06a79d13`,
stale/empty selection writes no notification marker, so sources `18`, `23`, and
`24` are eligible again after cursor wrap. This PR implements the required
nonterminal cooldown, but it is not yet deployed or production-validated.

## Current authorization state

Completed earlier one-attempt Web/Telegram gates consumed their authorizations. The later notification-proof PRELIVE made no Telegram attempt, so that authorization is unconsumed but retired as obsolete for this already-proven objective. Neither state authorizes another live action.

```text
PR27_WEB_CANARY_AUTHORIZATION_CONSUMED=YES
IDENTITY_ONLY_TELEGRAM_GATE_AUTHORIZATION_CONSUMED=YES
SOURCE_19_20_BOUNDED_TELEGRAM_PROBE_AUTHORIZATION_CONSUMED=YES
COLLECTOR_1_CLEANUP_AUTHORIZATION_CONSUMED=YES
COLLECTOR_1_CLEANUP_COMPLETED=YES
NOTIFICATION_PROOF_AUTHORIZATION_CONSUMED=NO
NOTIFICATION_PROOF_AUTHORIZATION_RETIRED_DUE_PREEXISTING_SENT_ROWS=YES
LIVE_CHECKPOINT_2_RETIRED=YES
PR32_NOTIFICATION_CANARY_AUTHORIZATION_CONSUMED=YES
PR32_NOTIFICATION_CANARY_RETRY_ALLOWED=NO
NEW_LIVE_ACTION_AUTHORIZED=NO
NEW_WEB_CANARY_AUTHORIZED=NO
NEW_TELEGRAM_SOURCE_PROBE_AUTHORIZED=NO
SOURCE_19_20_LIFECYCLE_MUTATION_AUTHORIZED=NO
OWNER_CANDIDATE_NOTIFICATION_AUTHORIZED=NO
CANDIDATE_NOTIFICATION_RECURRING_AUTOMATION_AUTHORIZED=NO
SOURCE_19_20_MEMBERSHIP_PROVISIONING_AUTHORIZED=NO
PERSISTENT_SOURCE_DISCOVERY_AUTHORIZED=NO
TELEGRAM_DISCOVERY_AUTHORIZED=NO
SOURCE_AUDIT_AUTHORIZED=NO
AUTO_APPROVE_AUTHORIZED=NO
AUTO_JOIN_AUTHORIZED=NO
PERSISTENT_RUNTIME_AUTHORIZED=NO
```

## Next gate

```text
NEXT_PRODUCT_GATE_AFTER_REVIEW_MERGE_SYNC=BOUNDED_COOLDOWN_VALIDATION
```

```text
1. independently review the exact cooldown implementation head
2. only after review PASS, request Owner merge authorization
3. merge the exact reviewed head
4. separately authorize production sync and migration to 20260914_0043
5. run a read-only exact-state PRELIVE
6. separately authorize one bounded stale/unresolvable probe
7. prove by read-only selection that immediate re-probe is suppressed before Telegram
8. only after that evidence, discuss recurring scheduling
```

The later cooldown validation must keep `relevance_class=strong` and the exact
active confirmed profile/current deterministic intent binding. This PR contains
no authorization or command for production sync, migration, Telegram, Owner
send, lifecycle mutation, Source Audit, Web, AI, scheduler, or persistent
runtime work.

Fresh exact-head server evidence remains higher authority than code/CLI, which remains higher authority than canonical docs, which remains higher authority than historical reports.
