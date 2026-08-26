# LeadRadar — Known Limitations and Validation Gaps

**Status:** CANONICAL  
**Last verified:** 2026-08-27  
**Implementation baseline:** `f9884b196ed6a424ec69352597de66c1eeca331c`

This document distinguishes code that exists from behavior that has actually
been validated in the current deployment.

## Immediate deployment blocker

The first bounded full-runtime canary ran safely for 600 seconds but received no
natural Telegram source messages.

Therefore the project still lacks live evidence for:

```text
Telegram event
-> raw_messages
-> cheap V2 prefilter
-> legacy-filter shadow row
```

This is currently the reason:

```text
READY_FOR_AI_SETUP=NO
```

The next step is a longer bounded natural-traffic observation, not AI or
catch-up.

## Current top limitations

1. **P0 — No live shadow evidence yet.** Raw/prefilter/shadow code is tested but
   no natural message arrived in the first deployment canary.
2. **P0 — No live AI Opportunity-analysis evidence.** The current deployment has
   no AI key configured by design.
3. **P0 — No live end-to-end lead delivery yet.** Matching and personalized
   delivery are implemented/tested, but no real Opportunity has been analyzed
   and delivered in this deployment.
4. **P1 — Source activity is external and can be sparse.** Thirteen sources are
   approved/readable, but a bounded window can legitimately receive zero posts.
5. **P1 — Telegram availability/account limits remain external.** FloodWait,
   account permissions, source removal/rename and private access can interrupt
   collection independently of PostgreSQL correctness.
6. **P1 — Legacy filter substring behavior can create false positives.** The
   accumulated stop-word matcher remains substring-based. It is intentionally
   preserved until shadow data supports a narrow redesign.
7. **P1 — AI quality/cost are provider-dependent.** Repository abstractions and
   tests do not establish that a particular current provider/model is suitable.
8. **P1 — SearchProfile onboarding requires a configured AI route for the
   natural-language flow.** That provider is not enabled in the current
   deployment.
9. **P1 — At-least-once external delivery remains.** Telegram send and
   PostgreSQL confirmation cannot be one atomic transaction; idempotency reduces
   but cannot mathematically remove the crash window.
10. **P2 — Discovery/audit code is not current deployment evidence.** Web,
    global/graph/chat discovery and Source Audit exist but are disabled and have
    not been rolled out on this deployment.
11. **P2 — Billing/payment code is not a configured production payment
    operation.** Provider-neutral state/adapters exist, but current private
    single-owner deployment has not activated production billing.
12. **P2 — Legacy V1 compatibility remains in the codebase.** SQLite/legacy
    components still exist even though PostgreSQL is V2 authority and legacy
    delivery is disabled.
13. **P2 — Synthetic/evaluation fixtures are not production-quality evidence.**
    Passing deterministic tests cannot substitute for bounded live validation.
14. **P2 — Persistent runtime is intentionally absent.** No LeadRadar daemon is
    currently authorized, so unattended continuity/restart behavior has not yet
    been proven on this server.

## Product semantics that can legitimately produce zero cards

Even after all runtime gates are enabled, zero user-facing matches is not
automatically a bug.

A card can be absent because of:

- no active SearchProfile;
- no approved/readable source traffic;
- no valid Opportunity;
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
distinction between test evidence and live positive owner evidence should remain
explicit.

## Historical documents

`PUBLIC_RELEASE_AUDIT.md` and `legacy-collector-migration.md` describe older
snapshots/intermediate gates and contain statements that are no longer current.

Use `docs/DOCUMENTATION_INDEX.md` and `docs/CURRENT_STATE.md` as current
authority.
