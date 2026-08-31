# LeadRadar

LeadRadar is an experimental Telegram freelance-opportunity discovery system
adapted from `Egor01KKK/telegram-freelance-lead-bot-v2`.

It combines a dedicated Telegram collector, PostgreSQL-backed durable ingestion,
high-recall filtering, optional AI Opportunity analysis, SearchProfiles,
deterministic matching and personalized Telegram delivery.

This repository is an engineering project, not a hosted service.

## Current project stage

As of the current documented implementation baseline
`d92b0446be19f391bb8f479387b27d914c081e35`:

- isolated PostgreSQL deployment is ready at Alembic `20260825_0037`;
- the dedicated Telegram collector is configured and joined to all 13 approved
  public sources;
- the bot is restricted to one owner account in private 1:1 chats;
- a natural Telegram message has been live-observed through `raw_messages`, the
  cheap V2 prefilter and `legacy-filter-shadow.v1` telemetry;
- shadow schema and exact filter SHA matched;
- no AI calls, Opportunities or deliveries occurred during that proof;
- the collector membership prerequisite has been experimentally confirmed;
- first-class OpenRouter support for V2 Opportunity Analysis is implemented and
  server-synced;
- the selected initial Opportunity Analysis route is
  `provider=openrouter`, `model=minimax/minimax-m3:free`;
- the OpenRouter runtime key is configured for the selected bounded
  Opportunity Analysis route, but no live AI provider call has occurred;
- this branch adds an explicit one-shot Opportunity Analysis job command for
  the first live AI canary;
- AI, discovery, catch-up and legacy delivery remain disabled;
- persistent runtime is **not** authorized.

Therefore the current next gate is a **bounded one-job live
Opportunity-analysis canary**, not full runtime or persistent deployment.

For exact state and next steps read
[`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) and
[`docs/ACTIVE_PLAN.md`](docs/ACTIVE_PLAN.md).

## For AI agents and new engineers

Start with [`AGENTS.md`](AGENTS.md), then follow
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
PostgreSQL APPROVED source
+ collector Telegram membership
-> Telegram live NewMessage
-> raw message + durable job
-> cheap high-recall prefilter
-> legacy filter shadow telemetry
-> optional AI Opportunity analysis
-> canonical Opportunity
-> SearchProfile matching
-> personalized owner-allowlisted delivery
```

PostgreSQL is the V2 source of truth. SQLite remains legacy compatibility only.

Important deployment nuance: being able to resolve/read a public Telegram
channel does not prove live update delivery. The dedicated collector must be a
channel participant/member. Current deployment membership is 13/13 approved
public sources.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Safety-first CLI

The default command is intentionally non-operational:

```bash
uv run --frozen python -m freelancer_bot
```

It prints help and exits.

Explicit network modes and diagnostics:

```bash
# Bot UI only.
uv run --frozen python -m freelancer_bot --bot-only

# Dedicated collector/source-side runtime without full ingestion/shadow.
uv run --frozen python -m freelancer_bot --collector-only

# Bounded networked source-access diagnostic using the Telegram user session.
# Resolves enabled config/sources.json entries but does not prove membership or
# live NewMessage delivery.
uv run --frozen python -m freelancer_bot --check-sources

# Process exactly one explicit opportunity.analysis.v1 durable job.
# Does not start Telegram, collector, discovery, matching or delivery runtime.
uv run --frozen python -m freelancer_bot --opportunity-analysis-job-id <UUID>

# Full collector + bot + durable ingestion/matching runtime.
uv run --frozen python -m freelancer_bot --run
```

`--check-sources` performs real Telegram requests and requires an explicitly
authorized bounded task. It is not a local/offline config check and is not a
membership-readiness proof.

`--opportunity-analysis-job-id` requires one explicit durable job UUID, verifies
that it is a claimable `opportunity.analysis.v1` job, processes at most that
selected job once through the production Opportunity Analysis path, then exits.
With `OPPORTUNITY_ANALYSIS_MAX_OUTPUT_ATTEMPTS=1` and
`OPPORTUNITY_ANALYSIS_FALLBACK_ENABLED=false`, one invocation can make at most
one provider request.

`--run` does not itself authorize discovery, catch-up, delivery or persistent
deployment. With a configured Opportunity Analysis provider key it can process
pending `opportunity.analysis.v1` jobs, so use the one-shot command for the
first bounded AI canary.

## Requirements

- Python 3.14.7
- uv 0.12.2
- PostgreSQL 18.x
- Telegram API ID/hash and dedicated user session for collection
- membership of the collector account in approved monitored channels
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

Never commit `.env` or session files. Telegram channel membership is external
account state and must be provisioned/verified separately from PostgreSQL source
seeding.

The current shared-server deployment has additional isolation rules in
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Owner-only bot access

For a private deployment:

```dotenv
TELEGRAM_ALLOWED_USER_IDS=<owner numeric Telegram ID>
```

When non-empty, bot interaction requires an allowlisted positive `sender_id`
from a private 1:1 chat. Group/supergroup interactions do not pass the gate.
Personalized delivery independently checks the recipient allowlist.

The collector account is independent from this bot allowlist.

## Sources and filtering

`config/sources.json` is repository seed/diagnostic input. Runtime source
lifecycle authority is PostgreSQL, while live Telegram collection additionally
requires collector membership in the approved channel.

`config/filters.json` contains preserved legacy keyword/stop-word rules.

In V2, the cheap prefilter is high-recall. The legacy filter is recorded as
**shadow telemetry**, not used as the V2 routing gate. No production filter
relaxation was required to prove the live ingestion/shadow path.

## AI and cost controls

AI is optional and BYOK.

The pre-AI ingestion gate has passed, and OpenRouter support is currently
implemented only for V2 Opportunity Analysis. It does not add first-class
OpenRouter support for reply drafting, SearchProfile onboarding, Source Audit,
Telegram Chat Screening or discovery.

The current deployment has the OpenRouter route configured for Opportunity
Analysis and still has zero live provider calls. The selected first route is
`minimax/minimax-m3:free`, whose availability and pricing must be reverified
immediately before live validation. Configuration readiness remains separate
from the first bounded live provider call.

Follow [`docs/ACTIVE_PLAN.md`](docs/ACTIVE_PLAN.md) and
[`docs/COST_SAFETY.md`](docs/COST_SAFETY.md).

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

Historical migration/publication notes remain in `docs/` but are not current
execution authority.

## License

MIT. See [`LICENSE`](LICENSE).
