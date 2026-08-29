# LeadRadar — Current Deployment

**Status:** CANONICAL  
**Snapshot date:** 2026-08-30
**Deployment code baseline:** `d92b0446be19f391bb8f479387b27d914c081e35`
**Repository/server head:** `d92b0446be19f391bb8f479387b27d914c081e35`

This document records the current shared-server LeadRadar layout. It contains no
credential values.

## Server isolation

LeadRadar checkout:

```text
/opt/leadradar/LeadRadar
```

Runtime state outside Git checkout:

```text
/opt/leadradar/runtime/.env
/opt/leadradar/runtime/sessions/
```

Project-local tooling:

```text
/opt/leadradar/LeadRadar/.venv
/opt/leadradar/tools/uv
/opt/leadradar/cache
```

Project Python:

```text
3.14.7
```

Do not modify shared-host global Python for LeadRadar work.

## PostgreSQL

Current isolated topology:

```text
container=leadradar-postgres
image=postgres:18.4-alpine
network=leadradar-net
volume=leadradar-postgres-data
host bind=127.0.0.1:55432
database=leadradar
role=leadradar
```

Expected state:

```text
POSTGRES_HEALTH=healthy
ALEMBIC_CURRENT=20260825_0037
```

Never print PostgreSQL credentials or the full credentialed `DATABASE_URL`.
Earlier exposed credentials were rotated and historical values are invalid.

## Telegram identities and sessions

Runtime session directory:

```text
/opt/leadradar/runtime/sessions
```

Active roles:

```text
freelancer_user          -> dedicated collector account
freelancer_delivery_bot  -> bot identity
```

The owner's main Telegram account is the bot user/recipient, not the collector.
The old main-account collector session is rollback-only and is not active.

Session files are bearer credentials. Collector and bot must use separate paths,
and two LeadRadar processes must not use the same session concurrently.

## Owner-only bot boundary

Runtime configuration has exactly one `TELEGRAM_ALLOWED_USER_IDS` entry: the
owner's main Telegram account. Its numeric value must not be recorded in docs or
reports.

With non-empty allowlist, inbound bot use requires an allowlisted positive
`sender_id` from a private 1:1 chat. Group/supergroup events fail closed.
Personalized delivery has an independent recipient allowlist check.

## Source catalog

Repository seed:

```text
config/sources.json
total=15
enabled=13
disabled=2
```

PostgreSQL runtime state:

```text
approved=13
candidate=2
```

PostgreSQL lifecycle/access state controls the monitored runtime snapshot.
`config/sources.json` is seed/diagnostic input, not a permissive fallback.

## Collector membership prerequisite

A critical deployment prerequisite is now proven:

> The dedicated collector must be a Telegram participant/member of an approved
> channel to receive that channel's live `NewMessage` updates.

Public-source resolution/history access is not enough. During investigation the
collector could resolve/read all approved sources while being a participant in
0/13; six natural messages occurred in three monitored sources during a
3600-second canary, yet no live callback fired.

After a controlled three-source join pilot, a natural message traversed:

```text
Telegram live update
-> raw_messages
-> cheap V2 prefilter
-> legacy-filter shadow
```

with valid schema/filter SHA and zero AI calls/Opportunities/deliveries.

Membership rollout is now complete:

```text
APPROVED_SOURCE_COUNT=13
MEMBER_AFTER_COUNT=13
NON_MEMBER_AFTER_COUNT=0
NEW_JOIN_SUCCESS_COUNT=10
NEW_JOIN_FAILURE_COUNT=0
COLLECTOR_MEMBERSHIP_ROLLOUT=COMPLETE
COLLECTOR_DEPLOYMENT_READY=YES
```

Membership is external Telegram account state. It is not stored as the source
lifecycle authority in PostgreSQL, so deployment/preflight procedures must
verify both:

```text
source APPROVED in PostgreSQL
AND
collector is Telegram member/participant
```

Do not add automatic join behavior without a separately reviewed design.

## Runtime flags

Current expected safe deployment flags:

```text
SEND_CATCH_UP=false
LEGACY_DELIVERY_ENABLED=false

SOURCE_DISCOVERY_ENABLED=false
SOURCE_AUDIT_ENABLED=false
SOURCE_GRAPH_DISCOVERY_ENABLED=false
TELEGRAM_CHAT_DISCOVERY_ENABLED=false

AI_REPLY_ENABLED=false
```

Current expected AI credential state:

```text
OPENAI_API_KEY=not configured
DEEPSEEK_API_KEY=not configured
TOKENROUTER_API_KEY=not configured
OPENROUTER_API_KEY=not configured
```

Current OpenRouter implementation state:

```text
OpenRouter Opportunity support present in checkout=YES
runtime OpenRouter configuration=NO
provider calls=0
```

`READY_FOR_OPENROUTER_CONFIGURATION=YES` means the implementation is deployed
and the pre-AI ingestion gate passed. It does **not** mean an OpenRouter key is
already configured or that live AI analysis is authorized.

## Process state

There is currently **no persistent LeadRadar runtime**.

Expected outside bounded tasks:

```text
application process=not running
collector=not running
bot=not running
user session lock=not held
```

No LeadRadar systemd unit is authorized.

## Current live validation

Validated:

```text
collector membership prerequisite=YES
approved source membership=13/13
live raw ingestion=YES
live cheap prefilter=YES
live legacy shadow=YES
shadow schema match=YES
shadow filter SHA match=YES
AI provider calls=0
live Opportunities=0
live deliveries=0
OPENROUTER_IMPLEMENTATION_READY=YES
OPENROUTER_RUNTIME_CONFIGURED=NO
READY_FOR_OPENROUTER_CONFIGURATION=YES
READY_FOR_BOUNDED_AI_ANALYSIS=NO
LIVE_AI_ANALYSIS_VALIDATED=NO
PERSISTENT_RUNTIME_AUTHORIZED=NO
```

The next gate is OpenRouter + MiniMax configuration-only, defined in
`docs/ACTIVE_PLAN.md`.

## Evidence references

Safe report hashes:

```text
investigation report:
cf5f14807005319ddf4862c36746904670ca04a1e9aa69a480650a792865eb12

membership pilot report:
f60769f6dcfbe65b7094ba7fba901fea9bc1e9a2278481c49265f83a9c50c623

membership rollout report:
dfbf1d19b29963c43e01eb9512e6817343a2274182be4c0d562466f0898cec5e

OpenRouter implementation sync report:
89decdcf40c3486d5cd51571ab2ab27d99049abb0d2158be602d11188bd4b369
```

## Shared-server no-touch boundary

LeadRadar shares the host with unrelated projects. LeadRadar tasks must not
modify:

- WayFound;
- Hermes;
- unrelated Docker containers/networks/volumes;
- unrelated systemd services;
- firewall;
- system time/NTP;
- global Python;
- unrelated databases.

A known Hermes restart-loop predates LeadRadar work and remains out of scope.

## Promotion rules

Before updating server checkout:

1. verify current HEAD;
2. verify tracked worktree clean;
3. fetch exact reviewed `origin/main`;
4. verify provenance/diff;
5. fast-forward only;
6. verify Alembic state;
7. preserve `/opt/leadradar/runtime`.

Code promotion, Telegram membership provisioning and runtime feature enablement
are separate actions.

## Secrets/reporting rules

Safe reports may contain commit SHAs, migration revisions, counts, booleans,
non-secret file hashes, public source handles and membership status.

Reports must not contain bot token, API hash, DB password/full DSN, owner numeric
Telegram ID, session contents, Telegram login/2FA codes, live message bodies or
AI provider keys.
