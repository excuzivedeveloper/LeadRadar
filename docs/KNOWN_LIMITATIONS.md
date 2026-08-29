# LeadRadar — Known Limitations and Validation Gaps

**Status:** CANONICAL  
**Last verified:** 2026-08-29  
**Implementation baseline:** `f9884b196ed6a424ec69352597de66c1eeca331c`

This document distinguishes code that exists from behavior that has actually
been validated in the current deployment.

## Pre-AI blocker status

The previous live-ingestion blocker is closed.

The project has now observed a natural Telegram message through:

```text
Telegram live update
-> raw_messages
-> cheap V2 prefilter
-> legacy-filter shadow row
```

with matching shadow schema/filter SHA and zero AI calls, Opportunities or
deliveries.

The root deployment prerequisite was Telegram channel membership of the dedicated
collector. Current approved-source membership is 13/13.

Therefore:

```text
SHADOW_LIVE_EVIDENCE=YES
READY_FOR_AI_SETUP=YES
```

The next limitation/gate is live AI configuration/validation, not ingestion.

## Current top limitations

1. **P0 — No live AI Opportunity-analysis evidence yet.** The deployment still
   has no AI provider key/model configured by design.
2. **P0 — No live end-to-end lead delivery yet.** Matching and personalized
   delivery are implemented/tested, but no real AI-produced Opportunity has been
   matched and delivered in this deployment.
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
8. **P1 — AI quality/cost are provider-dependent.** Repository abstractions and
   tests do not establish that a specific current provider/model is suitable.
9. **P1 — SearchProfile onboarding requires a configured AI route for its
   natural-language flow.** That route is not enabled yet.
10. **P1 — At-least-once external delivery remains.** Telegram send and
    PostgreSQL confirmation cannot be one atomic transaction; idempotency reduces
    but cannot mathematically remove the crash window.
11. **P2 — Discovery/audit code is not deployment evidence.** Web,
    global/graph/chat discovery and Source Audit exist but remain disabled.
12. **P2 — Billing/payment code is not configured production payment behavior.**
    Provider-neutral state/adapters exist, but current private single-owner
    deployment has not activated production billing.
13. **P2 — Legacy V1 compatibility remains in the codebase.** SQLite/legacy
    components still exist even though PostgreSQL is V2 authority and legacy
    delivery is disabled.
14. **P2 — Synthetic fixtures are not production-quality evidence.** Tests are
    necessary but do not substitute for bounded live validation.
15. **P2 — Persistent runtime is intentionally absent.** No LeadRadar daemon is
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
