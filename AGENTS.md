# LeadRadar — Agent Entry Point

**Status:** CANONICAL  
**Last verified:** 2026-08-27  
**Implementation baseline:** `f9884b196ed6a424ec69352597de66c1eeca331c`

This file is the entry point for ChatGPT, Codex, Claude, DeepSeek, or any other
engineer/agent that receives repository access without prior conversation
history.

## Mandatory reading order

Read these files before proposing implementation or server work:

1. `docs/DOCUMENTATION_INDEX.md`
2. `docs/CURRENT_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/ACTIVE_PLAN.md`
5. `docs/DEPLOYMENT.md`
6. `docs/DECISIONS.md`
7. `SECURITY.md`
8. `docs/COST_SAFETY.md`
9. `docs/KNOWN_LIMITATIONS.md`

Then inspect the code that is relevant to the requested task.

Do **not** start by reading historical notes and inferring the current state from
them. `docs/PUBLIC_RELEASE_AUDIT.md` and
`docs/legacy-collector-migration.md` are historical evidence, not current
execution authority.

## Source-of-truth precedence

When facts disagree, use this order:

1. fresh server/runtime evidence for deployment state;
2. code and migrations at the current repository head;
3. canonical current documentation listed above;
4. tests and CI;
5. historical documentation and old PR/task reports.

`docs/CURRENT_STATE.md` records an implementation/deployment snapshot. A later
docs-only commit can make repository `HEAD` differ from the implementation
baseline without changing runtime behavior. If code changes after the recorded
baseline, verify the diff and update the canonical docs in the same workstream.

## Project execution rules

- Do not redo a completed stage unless current evidence shows it is invalid.
- Follow `docs/ACTIVE_PLAN.md` in order. Do not skip a gate because later code
  already exists.
- Preserve the upstream Telegram anti-noise behavior unless an explicitly
  reviewed change says otherwise.
- The V2 cheap prefilter and legacy filter shadow have different roles. Do not
  silently turn the legacy filter back into the V2 gate.
- `config/sources.json` is seed/diagnostic input. The runtime source catalog is
  PostgreSQL-backed.
- PostgreSQL is the V2 source of truth. SQLite is legacy compatibility only.
- Never print or commit Telegram credentials, bot tokens, DB credentials,
  provider keys, session contents, owner numeric Telegram ID, or live message
  bodies.
- Any credential exposed during testing must be rotated before continuing.
- Server work is performed one command at a time with output review between
  commands.
- LeadRadar runs on a shared server. Do not modify unrelated containers,
  systemd services, firewall, global Python, WayFound, Hermes, or other
  databases.
- A bounded validation is not authorization for a persistent runtime.
- AI, discovery, catch-up, and delivery are separate gates. Enabling one does
  not authorize the others.

## Documentation invariant

Any PR that changes architecture, runtime modes, persistence, source lifecycle,
security boundaries, deployment flags, or the active execution order must update
the relevant canonical documentation in the same PR.

At minimum keep these synchronized:

- `docs/CURRENT_STATE.md` — what is true now;
- `docs/ACTIVE_PLAN.md` — what happens next;
- `docs/ARCHITECTURE.md` — how the system works;
- `docs/DEPLOYMENT.md` — what is deployed and how it is isolated;
- `docs/DECISIONS.md` — why important constraints exist.

The goal is that a new agent can read the repository in the mandatory order and
continue development without repeating completed work or accidentally enabling
a stage that has not passed its gate.
