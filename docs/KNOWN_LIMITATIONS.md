# LeadRadar — Known Limitations and Validation Gaps

**Status:** CANONICAL  
**Last verified:** 2026-09-18
**Implementation baseline:** production evidence at `b9177efdf10c9a2d0c8f191c08cc9a09d2ba0fe7`
**Latest verified production evidence head:** `b9177efdf10c9a2d0c8f191c08cc9a09d2ba0fe7`

This document distinguishes code that exists from behavior that has actually been validated in the current deployment.

## PR38 scheduler provenance boundary

The six historical scheduled fires are safe and bounded by available evidence,
but their trigger provenance remains indirect rather than direct: the journal
does not expose a per-job natural-timer caller field. This is an observability
gap, not evidence of a manual start or of an unsafe/failed run. PR38 adds a
systemd-level `RefuseManualStart=yes` contract so future explicit manual starts
are refused while indirect timer activation remains allowed. The timer remains
disabled pending full PR38 rollout and new activation authorization.

## Completed evidence status

The previous live-ingestion blocker is closed, the first bounded Opportunity Analysis canary passed, PR23 restored production SearXNG, PR27 repaired Profile Discovery Intent versioning, and the PR27 bounded Web canary has now completed successfully.

Current Web/Telegram evidence includes historical PR27–PR37 records and the
current PR38 state below:

```text
PR27_BOUNDED_WEB_CANARY=PASS
PROFILE_DISCOVERY_INTENT_V2_PERSISTED=YES
CURRENT_V2_CONFLICT_PRESENT=NO
NON_DIRECT_LIVE_YIELD_PROVEN=YES
NON_DIRECT_ONLY_LIVE_YIELD_PROVEN=NO
NOVELTY_IMPROVED=NO
CURRENT_TELETHON_SESSION_COLLECTOR_ACCOUNT_ID=2
CURRENT_SESSION_BINDING_PROVEN=YES
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
LIVE_CHECKPOINT_2_RETIRED=YES
SOURCE_19_20_JOIN_PERFORMED=NO
PR32_REVIEW=PASS
PR32_MERGED=YES
PR32_PRODUCTION_SYNC=PASS
PR32_PRODUCTION_POSTVERIFY=PASS
HIGH_RELEVANCE_GATE_SYNCED_TO_PRODUCTION=YES
PR32_NOTIFICATION_CANARY_RESULT=NO_SEND_STALE_OR_EMPTY
PR32_NOTIFICATION_CANARY_AUTHORIZATION_CONSUMED=YES
PR32_NOTIFICATION_CANARY_RETRY_ALLOWED=NO
PR33_PRODUCTION_DOCS_SYNC=PASS
PR36_MERGED=YES
PR36_REVIEWED_HEAD=2044c92288733b5dcc4fc6906c08bdb7bc53873f
HISTORICAL_PR36_MERGE_COMMIT=21842ef0fbc110babecd7c8b559c987076e795b0
HISTORICAL_GITHUB_MAIN_HEAD=21842ef0fbc110babecd7c8b559c987076e795b0
CURRENT_PRODUCTION_HEAD=b9177efdf10c9a2d0c8f191c08cc9a09d2ba0fe7
ALEMBIC_CURRENT=20260914_0043
BOUNDED_PROFILE_WEB_REPLENISHMENT=PASS_NEW_STRONG
NEW_CURRENT_STRONG_CANDIDATE_SOURCE_IDS=23,24,26
CURRENT_STRONG_CANDIDATE_SOURCE_IDS=18,23,24,26
SOURCE_23_NOTIFICATION_CANARY=NO_SEND_STALE_OR_EMPTY
SOURCE_24_NOTIFICATION_CANARY=NO_SEND_STALE_OR_EMPTY
SOURCE_26_NOTIFICATION_CANARY=PASS_SENT
POST_SCAN_CURSOR=18
OWNER_NOTIFICATION_COUNT=4
SOURCE_26_LIFECYCLE=candidate
SOURCE_26_MEMBERSHIP_PROVEN=NO
COOLDOWN_BACKOFF_IMPLEMENTED=YES
COOLDOWN_BACKOFF_PRODUCTION_VALIDATED=YES
SOURCE_18_STALE_24H_COOLDOWN_PRODUCTION_PROVEN=YES
SOURCE_18_IMMEDIATE_SELECTOR_SUPPRESSION_PRODUCTION_PROVEN=YES
UNRESOLVABLE_BACKOFF_LIVE_PROVEN=NO
RECURRING_NOTIFICATION_SCHEDULER_IMPLEMENTED=YES
OWNER_NOTIFICATION_SERVICE_INSTALLED=YES
OWNER_NOTIFICATION_SERVICE_ACTIVE=NO
OWNER_NOTIFICATION_TIMER_INSTALLED=YES
OWNER_NOTIFICATION_TIMER_ENABLED=NO
OWNER_NOTIFICATION_TIMER_ACTIVE=NO
OWNER_NOTIFICATION_TIMER_NEXT_TRIGGER_PRESENT=NO
PR38_HARDENING_INSTALLED_IN_PRODUCTION=NO
PERSISTENT_RUNTIME_AUTHORIZED=NO
PERSISTENT_RUNTIME=STOPPED
CURRENT_GATE=PR38_FINAL_CORRECTIVE_REREVIEW
TIMER_REACTIVATION_AUTHORIZED=NO
NEW_SCHEDULED_FIRE_AUTHORIZED=NO
PRODUCTION_SYNC_OF_PR38_AUTHORIZED=NO
PR38_MERGE_AUTHORIZED=NO
```

Historically, PR36 was merged on GitHub main at
`21842ef0fbc110babecd7c8b559c987076e795b0`
(`PR36_REVIEWED_HEAD=2044c92288733b5dcc4fc6906c08bdb7bc53873f`) before the
required independent-review and Owner merge-authorization gates were proven.
Post-merge independent technical review passed the implementation as safe to
keep on GitHub main with corrections handled historically by PR37. That history
does not define the current gate: service/timer units are installed, timer is
disabled/inactive, service is inactive, and PR38 hardening remains repository-
only pending corrective review and explicit authorization.

Useful personalized opportunity delivery remains a later product limitation. The narrower fact now proven is durable delivery persistence for source-candidate cards for sources `19` and `20`; that does not establish end-to-end matched-opportunity delivery or Owner review/action.

## Current top limitations

1. **P0 — PR27 improved search volume/support, but candidate novelty did not improve in the bounded sample.** The successful canary considered 19 search results and 18 Telegram-like matches versus PR23's 7 and 6, while both runs produced 4 unique candidates and 0 new candidates. Buyer-habitat/adjacent supplied live support to 3/4 unique candidates, so non-direct live support is proven. No non-direct-only candidate was produced, and novelty improvement is not proven.
2. **P0 — Source `19` and `20` remain candidates without lifecycle or membership proof.** `@phystechcareerchannel` and `@juniors_rabota_jobs` both resolved and exposed public history through the proven collector `2`, with fresh messages inside 10 days. Durable terminal rows prove their candidate cards were sent to the current Owner, but neither source was approved, rejected, joined or proven live-update-ready.
3. **P0 — Useful live owner delivery is not proven.** Matching and personalized delivery are implemented/tested, and prior bounded Opportunity Analysis/matching evidence exists, but useful current owner delivery has not yet been proven end-to-end.
4. **P0 — PR13 RU/EN web repair live result remains inconclusive.** PR13 is reviewed, merged and repeat-canaried, but the fresh sample was C++/HFT rather than a relevant RU/EN web sample.
5. **P1 — Lifecycle approval and Telegram membership are separate gates.** PostgreSQL `APPROVED` status plus public-history readability still does not guarantee Telegram live-update delivery. A future source approval requires explicit membership provisioning before collection readiness can be claimed.
6. **P1 — Telegram account/platform limits remain external.** FloodWait, ChannelsTooMuch, membership loss, source removal/rename and access changes can interrupt collection independently of PostgreSQL correctness.
7. **P1 — Membership drift is not automatically reconciled.** Previously approved source membership was brought to 13/13, but there is no authorized automatic join/remediation mechanism. Sources `19` and `20` were not joined by the new bounded probe.
8. **P1 — Candidate notification automation remains unauthorized.** PR32's bounded canary proved live current-profile/current-intent strong selection and freshness suppression, but produced no reservation or Owner card. PR34 later proved source-`18` stale 24-hour cooldown and immediate selector suppression. Historical source `19`/`20` sends predate the strong-only selector, and source `26` remains a candidate despite its sent card.
9. **P1 — Durable cooldown has a narrower remaining validation boundary.** The stale/empty 24-hour cooldown plus immediate pre-LIMIT selector suppression are production-proven for source `18`; unresolvable 6/12/24/48-hour escalation is not separately live-proven. The 3-hour/max-5 scheduler units are installed, its timer is disabled/inactive, reactivation is unauthorized, and PR38 hardening is not yet installed.
10. **P1 — Legacy filter substring behavior can create false positives.** The accumulated stop-word matcher remains substring-based. It is intentionally preserved until enough shadow data supports a narrow redesign.
11. **P1 — Current shadow sample is small.** Live path correctness is proven, but one successful natural shadow row is not enough to tune thresholds/keywords confidently.
12. **P1 — OpenRouter model availability/cost are external.** `minimax/minimax-m3:free` availability, pricing and rate/free-tier limits can change outside the repository and must be reverified before further live validation or expanded use.
13. **P1 — Opportunity Analysis has no separate enable switch.** Once the matching provider key is configured, full `--run` can process pending `opportunity.analysis.v1` jobs and make provider calls. `AI_REPLY_ENABLED` controls reply drafting only.
14. **P1 — SearchProfile onboarding requires a configured AI route for its natural-language flow.** That route is not enabled yet.
15. **P1 — At-least-once external delivery remains.** Telegram send and PostgreSQL confirmation cannot be one atomic transaction; idempotency reduces but cannot mathematically remove the crash window.
16. **P2 — OpenRouter scope is currently Opportunity Analysis only.** It is not first-class support for onboarding, Source Audit, Telegram Chat Screening, reply drafting or source discovery.
17. **P2 — Discovery/audit code is not autonomous deployment evidence.** Bounded PR27 Web execution is proven, but global/graph/chat discovery and Source Audit remain disabled. A successful bounded canary is not authorization for persistent discovery.
18. **P2 — Billing/payment code is not configured production payment behavior.** Provider-neutral state/adapters exist, but current private single-owner deployment has not activated production billing.
19. **P2 — Legacy V1 compatibility remains in the codebase.** SQLite/legacy components still exist even though PostgreSQL is V2 authority and legacy delivery is disabled.
20. **P2 — Synthetic fixtures are not production-quality evidence.** Tests are necessary but do not substitute for bounded live validation.
21. **P2 — PR14/PR15 OpportunityAnalysisV2 evidence-aware matching remains runtime shadow instrumentation only.** It is an observational evidence surface, not current matching or delivery policy.
22. **P2 — Persistent runtime is intentionally absent.** No LeadRadar daemon is authorized, so unattended continuity/restart behavior is not yet proven.
23. **P2 — PR21 Web-only provider evidence is a single historical sample.** The run ended after 5 of 12 selected queries due captcha/backoff, considered 12 search results, produced one weak new candidate, and is not enough to judge long-term source quality or novelty.
24. **P2 — Historical PR22 SearXNG engine removal was unsafe.** PR22 exact-engine removal was merged and production-synced, but activation proved unsafe for the pinned image because dependent Brave variants still referenced `network: brave`; PR23 restored SearXNG by preserving inherited engine/network definitions and disabling exact unwanted engines with `disabled: true`.
25. **P2 — Disabling those engines is not a guarantee against captcha/backoff.** It narrows known noisy defaults, but provider stability still depends on SearXNG defaults, upstream search behavior and local rate conditions.
26. **P2 — One-shot query bounds do not bound autonomous discovery.** `--max-queries` bounds an explicit operator run; persistent Web discovery remains unauthorized and separately unproven.
27. **P2 — Successful access/freshness probes do not validate the lifecycle service.** The source `19`/`20` gate intentionally did not call `SourceValidationService`; source and validation-table hashes remained unchanged. Treat it as access/freshness evidence only.
28. **P2 — Historical inactive collector row `1` remains persisted.** The duplicate-active anomaly is resolved and collector `2` is the sole active row. Collector `1` remains inactive for historical/FK continuity; its dependent operation-state row and historical references were intentionally preserved. This is not a blocker by itself, and its exact historical Telegram-user origin remains unproven.
29. **P2 — Recurring scheduling remains activation-limited.** Service/timer units are installed, but timer is disabled/inactive, service is inactive, and PR38 hardening is not installed. Six historical fires were bounded; direct caller provenance was unavailable. Reactivation requires PR38 corrective review and explicit authorization.

## PR27 bounded Web evidence boundary

The exact successful canary was:

```text
RUN_KEY=owner-profile-web-pr27-bounded-20260911-v1
DISCOVERY_RUN_ID=6a529712-6a7f-44a4-bd39-c8b23d25d44b
SEARCH_RESULTS_CONSIDERED=19
TELEGRAM_LIKE_CANDIDATES=18
UNIQUE_CANDIDATES=4
KNOWN_CANDIDATES=4
NEW_CANDIDATES=0
PERSISTED_V2_COUNT=1
CURRENT_V2_CONFLICT_PRESENT=NO
```

Angle attribution:

```text
DIRECT_UNIQUE_CANDIDATE_SUPPORT=4
BUYER_HABITAT_UNIQUE_CANDIDATE_SUPPORT=3
ADJACENT_UNIQUE_CANDIDATE_SUPPORT=3
DIRECT_ONLY_CANDIDATES=1
MIXED_DIRECT_AND_NON_DIRECT_CANDIDATES=3
NON_DIRECT_ONLY_CANDIDATES=0
NON_DIRECT_SUPPORTED_UNIQUE_CANDIDATES=3
```

Correct conclusion: non-direct queries supplied real support. Incorrect conclusions: that non-direct queries found a new source, produced a non-direct-only source, or improved novelty.

## Telegram access/freshness evidence boundary

The bounded probe used the proven current session / collector `2`, issued exactly four governed source operations, produced no FloodWait, and added exactly four operation events to collector `2` and none to other collectors.

```text
SOURCE_19=@phystechcareerchannel
SOURCE_19_HISTORY_READ=YES
SOURCE_19_FRESH_WITHIN_10_DAYS=YES
SOURCE_19_LIFECYCLE=candidate

SOURCE_20=@juniors_rabota_jobs
SOURCE_20_HISTORY_READ=YES
SOURCE_20_FRESH_WITHIN_10_DAYS=YES
SOURCE_20_LIFECYCLE=candidate

OWNER_NOTIFICATIONS_SENT=0
JOIN_LEAVE_REQUESTS=0
LIFECYCLE_TRANSITIONS_PERFORMED=NO
SOURCE_VALIDATION_SERVICE_CALLED=NO
```

Do not collapse these independent states:

```text
access/freshness
lifecycle approval
Telegram membership
Owner notification
persistent collection
```

## Owner candidate-notification evidence boundary

The later attempted notification proof failed safely in PRELIVE because durable target rows were already present. No Telegram network request or send was attempted by that gate, so its authorization was not consumed; the old live checkpoint is retired rather than retryable.

```text
SOURCE_19_20_NOTIFICATION_PRELIVE=FAIL_PREEXISTING_DURABLE_ROWS
TELEGRAM_NETWORK_ATTEMPTED=NO
BOT_SEND_ATTEMPTS=0
NOTIFICATION_PROOF_AUTHORIZATION_CONSUMED=NO
NOTIFICATION_PROOF_AUTHORIZATION_RETIRED_DUE_PREEXISTING_SENT_ROWS=YES
LIVE_CHECKPOINT_2_RETIRED=YES
RETRY_OR_LATE_CHECKPOINT2_ALLOWED=NO
```

Read-only diagnosis proved terminal `sent` rows for sources `19` and `20`, addressed to the current Owner, with consistent timestamps, Telegram message IDs and no failure codes. These are durable at-most-once markers under the unique `(recipient_chat_id, source_id)` contract; repeat notification is neither needed nor authorized.

Exact creating-command provenance is not persisted. The compatible notification timestamps, nearby collector-`2` governor events and durable scan state are explicitly `TEMPORAL/STRUCTURAL_INFERENCE`, not proof of an exact CLI command, process or direct event-row linkage.

This narrow delivery proof does not establish Owner review, lifecycle approval, membership, live-update readiness, useful personalized opportunity delivery or recurring notification automation. Both sources remain lifecycle `candidate`, and no join or lifecycle decision occurred.

## PR32 high-relevance canary boundary

The PR32 one-shot canary proved live Owner-profile resolution, deterministic
current-intent binding, exact strong-candidate selection, governed
entity/history access, freshness suppression, and cursor advancement to source
`18`. It ended `NO_SEND_STALE_OR_EMPTY` with zero reservation, notification-row
delta, send, and lifecycle-event delta.

`STALE_OR_EMPTY=1` does not reveal whether no usable latest-message timestamp
existed or the latest activity was older than 10 days. It must not be rewritten
as an exact timestamp or entity-resolution failure. PR32 did not live-prove the
reservation path, `mark_sent`, bot send, Owner-card delivery, or complete
high-relevance notification success. Its authorization is consumed and retry is
forbidden.

PR34 later recorded a nonterminal source-`18` stale probe-state row and proved
immediate pre-LIMIT selector suppression before Telegram. The scheduler units
are already installed and produced six bounded service invocations during the
earlier enabled interval; the timer is now disabled/inactive. PR38
`RefuseManualStart=yes` hardening exists only in the repository artifact and is
not installed/loaded in production. A new timer fire remains unauthorized until
PR38 review/merge/sync, installed-service update, daemon-reload/property
verification, and separate Owner reactivation authorization.

## What the historical membership investigation established

Earlier source accessibility checks showed approved public sources could be resolved/read. That was insufficient as a readiness test.

During a 3600-second canary, six natural messages occurred in three approved sources while the collector was a member of 0/13 channels; LeadRadar received no live raw messages. After joining three pilot sources, a natural message produced raw/prefilter/shadow evidence within 306 seconds, and remaining approved-source membership was later completed.

Consequences remain:

- zero raw messages were not caused by `min_score=7`;
- no collector-code defect was evidenced by that historical test;
- membership provisioning is an operational prerequisite;
- history readability is not a live-update readiness check.

## Product semantics that can legitimately produce zero cards

Even after all runtime gates are enabled, zero user-facing matches is not automatically a bug. A card can be absent because of no active SearchProfile, no fresh source traffic, no valid AI-classified Opportunity, deterministic matching thresholds/preferences, freshness, entitlement/subscription state, deduplication, or lifecycle state.

Do not weaken thresholds merely to force output.

## Owner-only access evidence boundary

Owner private `/start` has been validated live. Negative authorization scenarios are covered by reviewed tests. A live second-account abuse test is not required for the current gate, but test evidence and live positive owner evidence remain distinct.

## Historical documents

`PUBLIC_RELEASE_AUDIT.md` and `legacy-collector-migration.md` describe older snapshots/intermediate gates and contain statements that are no longer current.

Use `docs/DOCUMENTATION_INDEX.md`, `docs/PROJECT_LEARNINGS.md`, `docs/CURRENT_STATE.md`, `docs/ACTIVE_PLAN.md` and `docs/OPERATIONS.md` as current authority.
