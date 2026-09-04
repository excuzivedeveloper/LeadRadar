# LeadRadar — Known Limitations and Validation Gaps

**Status:** CANONICAL  
**Last verified:** 2026-09-04
**Implementation baseline:** `359dc17fbf4632e84b0a74f01ac201a426cf4556`

This document distinguishes code that exists from behavior that has actually
been validated in the current deployment.

## Completed blocker status

The previous live-ingestion blocker is closed, and the first bounded
Opportunity Analysis canary has passed.

The project has now observed a natural Telegram message through:

```text
Telegram live update
-> raw_messages
-> cheap V2 prefilter
-> legacy-filter shadow row
```

with matching shadow schema/filter SHA and no delivery.

The root deployment prerequisite was Telegram channel membership of the dedicated
collector. Current approved-source membership is 13/13.

Therefore:

```text
SHADOW_LIVE_EVIDENCE=YES
OPENROUTER_IMPLEMENTATION_READY=YES
OPENROUTER_RUNTIME_CONFIGURED=YES
OPENROUTER_API_KEY_CONFIGURED=YES
LIVE_AI_ANALYSIS_VALIDATED=YES
READY_FOR_OPENROUTER_CONFIGURATION=COMPLETE
READY_FOR_BOUNDED_AI_ANALYSIS=COMPLETE
PR13_REVIEWED=YES
PR13_MERGED=YES
PR13_REPEAT_BOUNDED_CANARY=COMPLETED
RUNTIME_STOPPED=YES
OUTSTANDING_JOBS=0
FRESH_NATURAL_LEAD=1
FRESH_SAMPLE=C++/HFT
OA_PIPELINE=PASS
MATCHING_PIPELINE=PASS
PR13_RU_EN_WEB_REPAIR_RESULT=INCONCLUSIVE_NO_RELEVANT_RU_EN_WEB_SAMPLE
USEFUL_DELIVERY_PROVEN=NO
READY_FOR_PERSISTENT_RUNTIME=NO
PR14_EVIDENCE_RUNTIME_INSTRUMENTATION_IMPLEMENTED=YES
SHADOW_RUNTIME_WIRED=YES
SHADOW_DURABLE_PERSISTENCE=YES
SHADOW_LIVE_VALIDATED=NO
PRODUCTION_MATCH_POLICY_CHANGED=NO
DELIVERY_POLICY_CHANGED=NO
```

The next limitation/gate is useful owner delivery from relevant live
Opportunity evidence, not ingestion or first-provider configuration.

## Current top limitations

1. **P0 — Useful live owner delivery is not proven.** Matching and
   personalized delivery are implemented/tested, and a fresh C++/HFT natural
   sample passed Opportunity Analysis and matching, but useful owner delivery
   has not yet been proven.
2. **P0 — PR13 RU/EN web repair live result is inconclusive.** PR13 is
   reviewed, merged and repeat-canaried, but the fresh sample was C++/HFT rather
   than a relevant RU/EN web sample.
3. **P1 — Collector membership is required external state.** PostgreSQL
   `APPROVED` status and public-history readability do not guarantee live update
   delivery. Deployment/preflight must also verify Telegram membership.
4. **P1 — Telegram account/platform limits remain external.** FloodWait,
   ChannelsTooMuch, membership loss, source removal/rename and access changes can
   interrupt collection independently of PostgreSQL correctness.
5. **P1 — Membership drift is not automatically reconciled.** Current rollout is
   13/13, but there is no authorized automatic join/remediation mechanism. A
   future source approval requires explicit membership provisioning.
6. **P1 — Legacy filter substring behavior can create false positives.** The
   accumulated stop-word matcher remains substring-based. It is intentionally
   preserved until enough shadow data supports a narrow redesign.
7. **P1 — Current shadow sample is small.** Live path correctness is proven, but
   one successful natural shadow row is not enough to tune thresholds/keywords
   confidently.
8. **P1 — OpenRouter model availability/cost are external.**
   `minimax/minimax-m3:free` availability, pricing and rate/free-tier limits can
   change outside the repository and must be reverified before further live
   validation or expanded use.
9. **P1 — Opportunity Analysis has no separate enable switch.** Once the
   matching provider key is configured, full `--run` can process pending
   `opportunity.analysis.v1` jobs and make provider calls. `AI_REPLY_ENABLED`
   controls reply drafting only.
10. **P1 — SearchProfile onboarding requires a configured AI route for its
   natural-language flow.** That route is not enabled yet.
11. **P1 — At-least-once external delivery remains.** Telegram send and
    PostgreSQL confirmation cannot be one atomic transaction; idempotency reduces
    but cannot mathematically remove the crash window.
12. **P2 — OpenRouter scope is currently Opportunity Analysis only.** It is not
    first-class support for onboarding, Source Audit, Telegram Chat Screening,
    reply drafting or source discovery.
13. **P2 — Discovery/audit code is not deployment evidence.** Web,
    global/graph/chat discovery and Source Audit exist but remain disabled.
14. **P2 — Billing/payment code is not configured production payment behavior.**
    Provider-neutral state/adapters exist, but current private single-owner
    deployment has not activated production billing.
15. **P2 — Legacy V1 compatibility remains in the codebase.** SQLite/legacy
    components still exist even though PostgreSQL is V2 authority and legacy
    delivery is disabled.
16. **P2 — Synthetic fixtures are not production-quality evidence.** Tests are
    necessary but do not substitute for bounded live validation.
17. **P2 — PR14/PR15 OpportunityAnalysisV2 evidence-aware matching is runtime
    shadow instrumentation only.** `PR14_EVIDENCE_RUNTIME_INSTRUMENTATION_IMPLEMENTED=YES`,
    `SHADOW_RUNTIME_WIRED=YES`, `SHADOW_DURABLE_PERSISTENCE=YES`,
    `PRODUCTION_MATCH_POLICY_CHANGED=NO`, `DELIVERY_POLICY_CHANGED=NO` and
    `SHADOW_LIVE_VALIDATED=NO`; the trace is an observational evidence surface,
    not current matching or delivery policy.
18. **P2 — Persistent runtime is intentionally absent.** No LeadRadar daemon is
    authorized, so unattended continuity/restart behavior is not yet proven.

## What the membership investigation changed

Earlier source accessibility checks showed all 13 approved public sources could
be resolved/read. That was insufficient as a readiness test.

During a 3600-second canary, six natural messages occurred in three approved
sources while the collector was a member of 0/13 channels; LeadRadar received no
live raw messages.

After joining three pilot sources, a natural message produced raw/prefilter/shadow
evidence within 306 seconds. The remaining 10 approved sources were then joined
successfully.

Consequences:

- zero raw messages were not caused by `min_score=7`;
- no collector-code defect is currently evidenced;
- membership provisioning is an operational prerequisite;
- `--check-sources` accessibility is not a live-update readiness check.

## Product semantics that can legitimately produce zero cards

Even after all runtime gates are enabled, zero user-facing matches is not
automatically a bug.

A card can be absent because of:

- no active SearchProfile;
- no fresh source traffic;
- no valid AI-classified Opportunity;
- deterministic matching thresholds/preferences;
- freshness;
- entitlement/subscription state;
- deduplication;
- lifecycle state.

Do not weaken thresholds merely to force output.

## Owner-only access evidence boundary

Owner private `/start` has been validated live.

Negative authorization scenarios (owner in group, non-private callback, missing
sender ID, non-allowlisted delivery) are covered by reviewed tests.

A live second-account abuse test is not required for the current gate, but the
distinction between test evidence and live positive owner evidence remains
important.

## Historical documents

`PUBLIC_RELEASE_AUDIT.md` and `legacy-collector-migration.md` describe older
snapshots/intermediate gates and contain statements that are no longer current.

Use `docs/DOCUMENTATION_INDEX.md`, `docs/CURRENT_STATE.md` and
`docs/ACTIVE_PLAN.md` as current authority.
