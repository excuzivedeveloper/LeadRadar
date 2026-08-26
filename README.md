# LeadRadar

LeadRadar is an experimental Telegram freelance-opportunity discovery system
adapted from `Egor01KKK/telegram-freelance-lead-bot-v2`.

It combines a dedicated Telegram collector, PostgreSQL-backed durable ingestion,
high-recall filtering, optional AI Opportunity analysis, SearchProfiles,
deterministic matching and personalized Telegram delivery.

This repository is an engineering project, not a hosted service.

## Current project stage

As of the current documented implementation baseline
`f9884b196ed6a424ec69352597de66c1eeca331c`:

- isolated PostgreSQL deployment is ready at Alembic `20260825_0037`;
- a dedicated Telegram account is configured for collection;
- 15 repository sources are seeded, 13 are approved/readable;
- the bot is restricted to one owner account in private 1:1 chats;
- V2 legacy-filter shadow telemetry is implemented;
- the first 600-second full-runtime canary started/stopped cleanly but received
  no natural source messages;
- AI, discovery, catch-up and legacy delivery remain disabled;
- persistent runtime is **not** authorized yet.

Therefore the current next gate is a longer bounded live shadow-evidence run,
not AI setup or daemon deployment.

For exact state and next steps read
[`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) and
[`docs/ACTIVE_PLAN.md`](docs/ACTIVE_PLAN.md).

## For AI agents and new engineers

Start with [`AGENTS.md`](AGENTS.md).

The canonical reading order is defined in
[`docs/DOCUMENTATION_INDEX.md`](docs/DOCUMENTATION_INDEX.md).

Do not infer current state from historical documents alone.

## Architecture in one page

Current identities:

```text
dedicated Telegram user account -> collector
owner main Telegram account     -> bot user/recipient
Telegram bot                    -> UI + delivery identity
```

Current steady-state V2 flow:

```text
approved PostgreSQL source
-> Telegram collector
-> raw message + durable job
-> cheap high-recall prefilter
-> legacy filter shadow telemetry
-> optional AI Opportunity analysis
-> canonical Opportunity
-> SearchProfile matching
-> personalized owner-allowlisted delivery
```

PostgreSQL is the V2 source of truth. SQLite remains legacy compatibility only.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Safety-first CLI

The default command is intentionally non-operational:

```bash
uv run --frozen python -m freelancer_bot
```

It prints help and exits.

Explicit network modes:

```bash
# Bot UI only; no collector/full ingestion runtime.
uv run --frozen python -m freelancer_bot --bot-only

# Dedicated collector/source-side runtime without the full ingestion runtime.
uv run --frozen python -m freelancer_bot --collector-only

# Full collector + bot + durable ingestion/matching runtime.
uv run --frozen python -m freelancer_bot --run
```

`--run` does not itself authorize AI, discovery, catch-up or persistent
deployment. Those remain explicit configuration/plan gates.

## Requirements

- Python 3.14.7
- uv 0.12.2
- PostgreSQL 18.x
- Telegram API ID/hash and user session for collection
- Telegram bot token for bot/full runtime
- provider key only when an AI capability is explicitly enabled

## Fresh local setup

```bash
git clone https://github.com/excuzivedeveloper/LeadRadar.git
cd LeadRadar

uv python install 3.14.7
uv sync --locked

cp .env.example .env
docker compose up -d postgres
uv run --frozen alembic upgrade head

uv run --frozen python -m freelancer_bot.persistence.source_seed \
  --sources-json config/sources.json

uv run --frozen python -m freelancer_bot --check-config
```

Never commit `.env` or session files.

The current shared-server deployment has additional isolation rules documented
in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Owner-only bot access

For a private deployment:

```dotenv
TELEGRAM_ALLOWED_USER_IDS=<owner numeric Telegram ID>
```

When non-empty, bot interaction requires an allowlisted positive `sender_id`
from a private 1:1 chat. Group/supergroup interactions do not pass the gate.

Personalized delivery also checks the allowlist before Telegram send.

The collector account is independent from this bot allowlist.

## Sources and filtering

`config/sources.json` is repository seed/diagnostic input. The runtime collector
uses PostgreSQL-approved source state.

`config/filters.json` contains the preserved legacy keyword/stop-word rules.

In V2, the cheap prefilter is intentionally high-recall. The legacy filter is
currently recorded as **shadow telemetry**, not used as the V2 routing gate.

See [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) for the current filter
snapshot and known matcher limitation.

## AI and cost controls

AI is optional and BYOK.

The current deployment intentionally has no AI key configured. Before enabling
AI, follow [`docs/ACTIVE_PLAN.md`](docs/ACTIVE_PLAN.md) and
[`docs/COST_SAFETY.md`](docs/COST_SAFETY.md).

Repository defaults include bounded attempts and Opportunity-analysis spend
guards, but provider/model/pricing choices still require operator verification.

## Security

Telethon sessions, bot tokens, Telegram API hashes, database credentials and
provider keys are bearer-sensitive material.

Do not paste live message bodies or credentials into issues, reports or chats.

See [`SECURITY.md`](SECURITY.md).

## Development and tests

```bash
uv sync --locked
uv run --frozen python -m unittest discover -s tests
uv run --frozen python -m py_compile \
  freelancer_bot/*.py freelancer_bot/persistence/*.py \
  migrations/*.py migrations/versions/*.py
uv run --frozen alembic check
git diff --check
```

Tests should use fakes/fixtures for Telegram/provider/payment/Web behavior unless
a task explicitly authorizes a bounded live test.

## Documentation

Canonical documentation:

- [`AGENTS.md`](AGENTS.md)
- [`docs/DOCUMENTATION_INDEX.md`](docs/DOCUMENTATION_INDEX.md)
- [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/ACTIVE_PLAN.md`](docs/ACTIVE_PLAN.md)
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- [`docs/DECISIONS.md`](docs/DECISIONS.md)
- [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md)
- [`docs/COST_SAFETY.md`](docs/COST_SAFETY.md)

Historical migration/publication notes remain in `docs/` but are explicitly not
the current execution authority.

## License

MIT. See [`LICENSE`](LICENSE).
