# Contributing to LeadRadar

## Scope

Keep changes small, auditable and provider-neutral where practical.

Do not add live credentials, Telegram sessions, captured private messages,
database dumps or secret-bearing generated reports to a pull request.

Before changing behavior, read:

1. `AGENTS.md`
2. `docs/CURRENT_STATE.md`
3. `docs/ARCHITECTURE.md`
4. `docs/ACTIVE_PLAN.md`
5. `docs/DECISIONS.md`

## Local setup

```bash
uv sync --locked
cp .env.example .env
uv run --frozen python -m freelancer_bot
```

The no-argument command is intentionally safe help.

Use `--bot-only`, `--collector-only` or `--run` only for an explicitly
controlled network test. Treat `--check-sources` the same way for authorization
purposes: it is a bounded Telegram network diagnostic using the user session,
not an offline config check.

## Verification

Before opening a PR:

```bash
uv run --frozen python -m unittest discover -s tests
uv run --frozen python -m py_compile \
  freelancer_bot/*.py freelancer_bot/persistence/*.py \
  migrations/*.py migrations/versions/*.py
uv run --frozen alembic check
git diff --check
```

PostgreSQL-backed tests use `TEST_DATABASE_URL`.

Provider, Telegram, payment and Web tests should use fakes/local fixtures unless
the task explicitly authorizes a bounded live call.

## Data and secrets

Use temporary test databases and temporary session paths.

Keep `.env`, sessions, SQLite files, logs, reports and artifacts ignored.

If a secret is exposed:

1. stop the affected live stage;
2. rotate/invalidate the credential;
3. update runtime configuration without printing the replacement;
4. report only credential class/status, not value.

## Behavioral invariants

Preserve unless the PR explicitly changes and reviews them:

- PostgreSQL V2 authority;
- append-only/auditable evidence;
- durable-job idempotency;
- SearchProfile ownership isolation;
- source lifecycle/access checks;
- collector/bot session separation;
- owner-only inbound/outbound boundaries in private deployment;
- legacy-filter shadow semantics;
- bounded cost/retry behavior.

Do not weaken match thresholds merely to make a synthetic/demo card appear.

## Documentation synchronization

Documentation is part of the feature.

A behavior-changing PR must update the canonical docs it makes stale.

At minimum review:

- `docs/CURRENT_STATE.md`
- `docs/ARCHITECTURE.md`
- `docs/ACTIVE_PLAN.md`
- `docs/DEPLOYMENT.md`
- `docs/DECISIONS.md`
- `docs/KNOWN_LIMITATIONS.md`

Historical documents should remain historical rather than being silently
rewritten as if they were current evidence.

A new agent should be able to read `AGENTS.md` and
`docs/DOCUMENTATION_INDEX.md`, understand what is implemented/live-validated,
and identify the exact next gate without access to old chat history.
