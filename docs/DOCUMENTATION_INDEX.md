# LeadRadar Documentation Index

**Status:** CANONICAL  
**Last verified:** 2026-08-27  
**Implementation baseline:** `f9884b196ed6a424ec69352597de66c1eeca331c`

This index defines which documents describe the current project and which are
historical/reference material.

## Start here

For a new engineer or AI agent, read in this exact order:

1. [`../AGENTS.md`](../AGENTS.md) — execution rules and precedence.
2. [`CURRENT_STATE.md`](CURRENT_STATE.md) — exact current implementation and
   deployment stage.
3. [`ARCHITECTURE.md`](ARCHITECTURE.md) — runtime identities, modes, data flow,
   persistence and security boundaries.
4. [`ACTIVE_PLAN.md`](ACTIVE_PLAN.md) — ordered next work and gates.
5. [`DEPLOYMENT.md`](DEPLOYMENT.md) — current server topology and operational
   constraints.
6. [`DECISIONS.md`](DECISIONS.md) — architectural decisions that must not be
   casually reversed.
7. [`../SECURITY.md`](../SECURITY.md) — credentials, sessions, allowlist and
   incident response.
8. [`COST_SAFETY.md`](COST_SAFETY.md) — AI/network spend and bounded-work rules.
9. [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) — what is still unverified or
   incomplete.

After that, inspect code and tests for the task at hand.

## Canonical current documents

| Document | Purpose |
| --- | --- |
| `AGENTS.md` | Agent entry point, source-of-truth precedence, execution rules |
| `README.md` | Public project overview and safe setup |
| `docs/CURRENT_STATE.md` | Current implementation/deployment snapshot |
| `docs/ARCHITECTURE.md` | Current system architecture and data flow |
| `docs/ACTIVE_PLAN.md` | Exact ordered execution plan |
| `docs/DEPLOYMENT.md` | Current LeadRadar server layout and boundaries |
| `docs/DECISIONS.md` | Accepted architectural decisions |
| `SECURITY.md` | Security policy and credential handling |
| `docs/COST_SAFETY.md` | External-work and AI cost controls |
| `docs/KNOWN_LIMITATIONS.md` | Current limitations and validation gaps |
| `docs/profile-setup.md` | Current V2 SearchProfile vs legacy reply-profile setup |
| `CONTRIBUTING.md` | Development, tests, and documentation synchronization |

## Contract/reference material

These are authoritative for their narrow schemas/configuration surfaces but do
not describe the current deployment stage:

- `.env.example`
- `docs/contracts/search-profile.schema.json`
- `docs/contracts/opportunity-analysis.schema.json`
- `docs/contracts/source-audit.schema.json`
- Alembic migrations under `migrations/versions/`
- `config/filters.json`
- `config/sources.json`

## Historical documents

### `docs/PUBLIC_RELEASE_AUDIT.md`

Historical publication audit from an older repository state. It records
`a378cf4` and migration head `20260818_0036`. The current migration head is
`20260825_0037`. Use it only for historical security/publication evidence.

### `docs/legacy-collector-migration.md`

Historical G0/G3/G4 migration notes. Useful for understanding compatibility
constraints and why legacy behavior exists, but individual statements describe
intermediate gates and may no longer reflect the current runtime.

Do not use either historical document as the current execution plan.

## Staleness rule

A canonical document should contain a verification date and implementation
baseline where appropriate. If a code-changing commit lands after that baseline:

1. inspect the code diff;
2. determine which canonical docs are affected;
3. update them before treating documentation as fully synchronized.

A docs-only commit may change repository `HEAD` while leaving the implementation
baseline unchanged. That is expected and should not be interpreted as a runtime
code change.
