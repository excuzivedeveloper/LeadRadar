# LeadRadar Documentation Index

**Status:** CANONICAL  
**Last verified:** 2026-09-10  
**Implementation baseline:** `1299e64f28886dffe3b4bb0ddc201952aa8a2a28`

This index defines which documents describe the current project and which are historical/reference material.

## Start here

`AGENTS.md` is the unconditional repository entry point. After it, read canonical material in this order:

1. [`PROJECT_LEARNINGS.md`](PROJECT_LEARNINGS.md) — operational lessons that prevent repeated false assumptions.
2. [`CURRENT_STATE.md`](CURRENT_STATE.md) — current implementation and deployment snapshot.
3. [`ARCHITECTURE.md`](ARCHITECTURE.md) — runtime identities, modes, data flow, persistence and security boundaries.
4. [`ACTIVE_PLAN.md`](ACTIVE_PLAN.md) — exact ordered next work and gates.
5. [`OPERATIONS.md`](OPERATIONS.md) — verified production commands, CLI namespaces, DB/Alembic contract, containers, ports, safety flags and runbook rules.
6. [`DEPLOYMENT.md`](DEPLOYMENT.md) — current server topology and deployment boundaries.
7. [`DECISIONS.md`](DECISIONS.md) — accepted architectural decisions.
8. [`../SECURITY.md`](../SECURITY.md) — credentials, sessions, allowlist and incident response.
9. [`COST_SAFETY.md`](COST_SAFETY.md) — AI/network spend and bounded-work rules.
10. [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) — current limitations and validation gaps.

After that, inspect exact code and tests for the task at hand.

## Canonical current documents

| Document | Purpose |
| --- | --- |
| `AGENTS.md` | Agent entry point, source-of-truth precedence, execution rules |
| `README.md` | Public project overview and safe setup |
| `docs/PROJECT_LEARNINGS.md` | Operational lessons learned from bounded gates and server evidence |
| `docs/CURRENT_STATE.md` | Current implementation/deployment snapshot |
| `docs/ARCHITECTURE.md` | Current system architecture and data flow |
| `docs/ACTIVE_PLAN.md` | Exact ordered execution plan |
| `docs/OPERATIONS.md` | Canonical production operational contract and command catalog |
| `docs/DEPLOYMENT.md` | Current LeadRadar server layout and no-touch boundaries |
| `docs/DECISIONS.md` | Accepted architectural decisions |
| `SECURITY.md` | Security policy and credential handling |
| `docs/COST_SAFETY.md` | External-work and AI cost controls |
| `docs/KNOWN_LIMITATIONS.md` | Current limitations and validation gaps |
| `docs/profile-setup.md` | Current V2 SearchProfile vs legacy reply-profile setup |
| `CONTRIBUTING.md` | Development, tests, and documentation synchronization |

## Operational source-of-truth rule

For production commands and server tasks, use this precedence:

```text
1. fresh server evidence at the exact production HEAD
2. exact repository code and `--help` at that HEAD
3. docs/OPERATIONS.md
4. DEPLOYMENT.md / CURRENT_STATE.md / ACTIVE_PLAN.md
5. historical reports
```

If a canonical document disagrees with fresh exact-head evidence, stop and reconcile documentation before designing a new live task.

## Contract/reference material

These are authoritative for their narrow schemas/configuration surfaces but do not describe the current deployment stage:

- `.env.example`
- `docs/contracts/search-profile.schema.json`
- `docs/contracts/opportunity-analysis.schema.json`
- `docs/contracts/source-audit.schema.json`
- Alembic migrations under `migrations/versions/`
- `config/filters.json`
- `config/sources.json`

## Historical documents

`docs/PUBLIC_RELEASE_AUDIT.md` and `docs/legacy-collector-migration.md` are historical/reference material. Do not use them as current execution plans.

## Staleness rule

A canonical document should contain a verification date and implementation baseline where appropriate. If a code-changing or deployment-changing commit lands after that baseline:

1. inspect the exact diff and server evidence;
2. determine which canonical docs are affected;
3. update them before treating documentation as synchronized;
4. never copy an old operational command forward without rechecking its entrypoint and argument contract.
