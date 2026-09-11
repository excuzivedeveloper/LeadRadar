# LeadRadar — Project Learnings

**Status:** CANONICAL  
**Last verified:** 2026-09-11

This file records operational lessons that should shape future implementation, review and server work. Read it immediately after `docs/DOCUMENTATION_INDEX.md`.

## Current lessons

- **Implementation state and production state are separate facts.** A reviewed repository change is not production behavior until the exact reviewed commit is merged, synced to the server and activated where needed.
- **Canonical docs can lag current `main` or server evidence.** Prefer fresh exact-head server evidence first, then exact code/CLI help, then canonical docs. Reconcile stale docs before using them to design a new live task.
- **Production commands must come from the verified operational contract, not memory or analogy.** Before a new command family is used on production, verify its actual module entrypoint, `--help`, runtime interpreter, DB API, schema names and required env loading at the exact target commit.
- **Application CLI and operator CLI are different interfaces.** `./.venv/bin/python -m freelancer_bot` invokes the application/runtime CLI; bounded operator commands live under `./.venv/bin/python -m freelancer_bot.operator_cli`. Never assume subcommands from one namespace exist in the other.
- **The production Python executable is project-local.** Current production uses `./.venv/bin/python` with Python `3.14.7`; a bare `python` executable is absent. Server tasks must not guess interpreter names.
- **LeadRadar DB access is SQLAlchemy async, not asyncpg direct.** `Database.connect()` yields SQLAlchemy `AsyncConnection`; use `connection.execute(...)` and `connection.scalar(...)`. Do not invent `fetchval`, `fetchrow` or `fetch` calls unless the exact code path actually returns an asyncpg connection.
- **Schema field names must be verified from exact code.** Current source lifecycle is `sources.lifecycle_status`, and `SourceStatus.CANDIDATE` is `candidate`. Do not translate concepts into guessed column names such as `lifecycle_state`.
- **Alembic production commands need the canonical runtime env.** `migrations/env.py` resolves the DSN through `RuntimeConfig.from_env(mode=DATABASE)` when `sqlalchemy.url` is absent, so load `/opt/leadradar/runtime/.env` before DB-connected `alembic current`. Never print `DATABASE_URL`.
- **A one-shot query bound is not a persistent-runtime bound.** The `profile-discovery run --max-queries` contract bounds that explicit operator invocation only. It does not authorize or bound unattended persistent source discovery.
- **A one-attempt Owner authorization is consumed when the authorized invocation command is issued.** Even a CLI parse rejection consumes that authorization if the task defined invocation itself as the consumption point. A new live attempt then needs a fresh authorization and run key.
- **Do not retry a failed live Web invocation under the same authorization.** A runtime failure before `discovery_runs` creation still consumes the one-attempt authorization once the invocation is issued. The run key `owner-profile-web-pr24-bounded-20260911-v1` is retired even though no run row was created.
- **CLI parse rejection is not provider evidence.** If argument parsing prevents Web Discovery from starting, do not interpret zero results as SearXNG failure, PR24 yield failure or successful bounded discovery.
- **Profile Discovery Intent content changes require a new intent version.** The deterministic intent UUID includes the intent version, profile identity and profile revision. If generated persisted intent content changes, keep historical rows immutable and bump the intent contract version rather than weakening `ensure()` or changing the SearchProfile revision.
- **Web provider backoff is evidence, not permission to retry.** A degraded provider state such as `BACKOFF` documents what happened and should inform the next reviewed gate; it is not authorization for an immediate second live run.
- **SearXNG default engine inheritance matters.** `use_default_settings: true` inherits default engines even when the local settings file has no explicit engine list.
- **SearXNG engine removal can break network aliases.** Before removing an inherited engine, inspect whether retained engines declare `network: <engine-name>`. Removing a base engine can break initialization even if that engine itself is unwanted.
- **Prefer disabled SearXNG overrides when network identity must remain.** For an unwanted default engine that is also a network provider for retained variants, use an exact local override with `disabled: true` rather than deleting the definition.
- **SearXNG config-schema validity is not runtime-init validity.** A YAML parse or settings-loader merge passing does not prove `searx.search.initialize()` will succeed. Image-specific startup/init validation is required for engine-topology changes.
- **Production runtime env must preserve Compose interpolation.** A Compose file using `${SEARXNG_PORT:-8080}` silently falls back to 8080 if the runtime variable is absent. The verified LeadRadar production port is `SEARXNG_PORT=8888`.
- **Container runtime must be discovered, not guessed.** The verified SearXNG interpreter is `/usr/local/searxng/.venv/bin/python3`; generic `docker exec ... python` is not reliable.
- **Docker exec heredoc diagnostics require stdin attachment.** Use `docker exec -i` when passing a heredoc or stdin-driven script into the container.
- **Read-only diagnostics do not authorize repair.** Inspecting server state, container settings, database rows or provider evidence does not grant permission to restart, recreate, write, retry or repair.
- **Failed read-only checkpoints are hard-stop gates.** If an authorized read-only checkpoint fails or mismatches, stop immediately. Alternate commands, repairs or retries require a newly defined task unless the existing task explicitly permits them.
- **Do not repeat already-proven checkpoints without a reason.** When a task fails because of a verification-command defect, a continuation task should normally resume from the failed point after re-establishing only the minimum continuity necessary.
- **SearXNG and the LeadRadar persistent runtime are separate services.** A SearXNG config/restart gate does not authorize the LeadRadar app/bot/collector persistent runtime, and a LeadRadar runtime gate does not imply SearXNG config activation.
- **Operational documentation should preserve exact facts and side-effect classes.** Record commit SHAs, paths, module entrypoints, arguments, migration revisions, container names, ports, schema names, safety flags and whether a command is read-only, Web-live, Telegram-live or mutating.
- **Counts are evidence snapshots, not contracts.** Current discovery/source/telemetry counts may change naturally. Use them to establish before/after deltas, but treat schema names, API surfaces and lifecycle semantics as the durable operational contract.
