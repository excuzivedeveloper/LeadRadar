# LeadRadar Security Policy

**Current policy verified:** 2026-08-27

LeadRadar uses Telegram user sessions, a bot identity, PostgreSQL and optional
external AI/Web providers. Treat all bearer credentials and session material as
security-sensitive.

## Never publish or paste

Do not commit or paste:

- `.env` files or secret previews;
- Telethon `*.session`, lock, journal, WAL or session strings;
- PostgreSQL passwords or credentialed DSNs;
- Telegram API hash or bot token;
- Telegram login/2FA codes;
- owner numeric Telegram ID in public reports;
- OpenAI, DeepSeek, TokenRouter, Brave, SearXNG, OAuth, webhook or cookie
  credentials;
- raw/private Telegram message bodies;
- private-source access material.

Synthetic token-shaped test fixtures are not credentials.

## If a secret is exposed

Treat the actual value as compromised.

- Bot token: revoke/regenerate with official BotFather and replace it in runtime
  configuration.
- Telegram user session: terminate the affected session in Telegram Devices and
  re-authenticate to a fresh local session path.
- Telegram API hash: treat as compromised and perform explicit API credential
  remediation.
- PostgreSQL password/credentialed DSN: rotate the role password and update the
  runtime env atomically.
- AI/Web/payment key: revoke and replace at the provider.

Do not paste the replacement value into chat or an issue.

LeadRadar setup/diagnostic work has already exercised this policy: credentials
that were exposed were rotated before later live stages continued. Historical
values must not be reused.

## Telegram identity separation

Current private deployment uses:

```text
dedicated user account -> collector
owner main account     -> bot user
bot identity           -> UI/delivery
```

Collector and bot must use separate Telethon session files.

Do not run concurrent processes against the same session path.

## Owner-only bot access

BotFather configuration and a hidden username are not an authorization boundary.

`TELEGRAM_ALLOWED_USER_IDS` is the application-level bot allowlist.

With a non-empty allowlist, inbound authorization must require:

```text
positive exact integer sender_id
sender_id present in allowlist
private 1:1 Telegram event
```

Do not authorize by `chat_id` fallback.

Unauthorized/non-private events must be rejected before:

- user/subscriber creation;
- SearchProfile read/write;
- onboarding/provider calls;
- navigation state mutation;
- delivery-action mutation;
- private product-state disclosure.

Outbound personalized delivery has an independent recipient allowlist check.

The bot allowlist must not restrict the dedicated collector.

## Persistence/runtime boundaries

- PostgreSQL is the V2 source of truth.
- Alembic is the schema change path.
- SQLite is legacy compatibility only.
- `config/sources.json` is seed/diagnostic input, not a permissive runtime
  fallback.
- no-argument CLI is safe help only;
- `--bot-only`, `--collector-only`, `--run` are explicit network modes;
- AI/discovery/catch-up flags are independent opt-ins.

Missing provider credentials must fail closed or make the optional feature
unavailable. They must not cause an unbounded retry loop.

## Shared-server isolation

LeadRadar is deployed on a shared host.

A LeadRadar task must not modify unrelated:

- Docker containers/volumes/networks;
- systemd services;
- firewall;
- global Python;
- system clock/NTP;
- databases;
- WayFound/Hermes or other project state.

## Logging and evidence

Structured logs attempt to redact configured secrets and message content, but
operators must not rely on redaction as permission to print secrets.

Prefer evidence containing:

- IDs;
- counts;
- hashes of non-secret config files;
- statuses;
- bounded metrics.

Do not include raw message bodies or credential values in issue reports.

## Reporting vulnerabilities

Provide a minimal reproduction, affected file/symbol, concrete impact and
proposed correction without credentials/private data.

Use a private maintainer/security channel when available.

This project is not intended for spam, credential sharing, unauthorized source
access or bypassing Telegram/provider limits.
