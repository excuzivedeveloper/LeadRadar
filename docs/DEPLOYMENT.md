# LeadRadar — Current Deployment

**Status:** CANONICAL  
**Snapshot date:** 2026-08-27  
**Deployment code baseline:** `f9884b196ed6a424ec69352597de66c1eeca331c`

This document records the current shared-server LeadRadar layout. It contains no
credential values.

## Server isolation

LeadRadar is installed under:

```text
/opt/leadradar/LeadRadar
```

Runtime state is outside the Git checkout:

```text
/opt/leadradar/runtime/.env
/opt/leadradar/runtime/sessions/
```

Project-local tools/state include:

```text
/opt/leadradar/LeadRadar/.venv
/opt/leadradar/tools/uv
/opt/leadradar/cache
```

Project Python:

```text
3.14.7
```

The shared host's global Python is unrelated to LeadRadar and must not be
modified.

## PostgreSQL

Current isolated database topology:

```text
container=leadradar-postgres
image=postgres:18.4-alpine
network=leadradar-net
volume=leadradar-postgres-data
host bind=127.0.0.1:55432
database=leadradar
role=leadradar
```

Resource limits were created specifically for LeadRadar.

Current expected health:

```text
POSTGRES_HEALTH=healthy
ALEMBIC_CURRENT=20260825_0037
```

Never print the PostgreSQL password or full credentialed `DATABASE_URL`.

Credentials exposed during setup/diagnostics were rotated. Historical values
must be treated as invalid.

## Telegram sessions

Runtime session directory:

```text
/opt/leadradar/runtime/sessions
```

Active roles:

```text
freelancer_user          -> dedicated collector account
freelancer_delivery_bot  -> bot identity
```

The old main-account collector session was preserved only as rollback evidence
and is not the active collector path.

Session files are bearer credentials and must remain private with restrictive
permissions.

Do not run two LeadRadar processes against the same session path.

## Bot owner boundary

Runtime configuration has:

```text
TELEGRAM_ALLOWED_USER_IDS configured
entry count = 1
```

The single entry is the owner's main Telegram account.

Do not record its numeric value in documentation or reports.

The merged access policy requires a private 1:1 chat and valid allowlisted
`sender_id`; group/supergroup events are rejected.

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
repository_seed approved=13
repository_seed candidate=2
```

All 13 approved sources were accessible during setup validation.

The current runtime does not read JSON as a permissive fallback for monitored
sources. PostgreSQL lifecycle/access state controls the approved snapshot.

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
```

Do not infer an API key value from these status statements.

## Process state

There is currently **no persistent LeadRadar runtime**.

Expected outside a bounded test:

```text
application process=not running
collector=not running
bot=not running
user session lock=not held
```

No LeadRadar systemd unit has been authorized.

A bounded canary starts the repository process in the foreground and must stop it
again before the task is considered complete.

## Current live validation

A 600-second `--run` canary completed with graceful shutdown and no runtime
error, but no natural Telegram messages arrived.

Therefore:

```text
startup/shutdown safety=validated
live raw ingestion evidence=absent
live shadow evidence=absent
AI setup authorization=no
persistent runtime authorization=no
```

The next bounded run is defined by `docs/ACTIVE_PLAN.md`.

## Shared-server no-touch boundary

LeadRadar shares the host with unrelated projects.

LeadRadar tasks must not modify:

- WayFound;
- Hermes;
- unrelated Docker containers/networks/volumes;
- unrelated systemd services;
- firewall;
- system time/NTP;
- global Python;
- unrelated PostgreSQL databases.

A known unrelated Hermes service problem predates LeadRadar work and remains out
of scope unless separately authorized.

## System clock

The host has previously reported NTP synchronization as unavailable/not
synchronized, with only small observed Telegram setup skew.

Do not change system time or NTP as part of normal LeadRadar work without
separate authorization.

## Promotion rules

Before updating the server checkout:

1. verify current server HEAD;
2. verify tracked worktree is clean;
3. fetch exact reviewed `origin/main`;
4. verify merge provenance if relevant;
5. fast-forward only;
6. verify Alembic state;
7. do not overwrite `/opt/leadradar/runtime`.

Code promotion and runtime feature enablement are separate actions.

## Secrets/reporting rules

Safe reports may contain:

- commit SHAs;
- migration revision;
- counts;
- booleans;
- file modes;
- hashes of non-secret config snapshots;
- source handles when already public.

Reports must not contain:

- bot token;
- API hash;
- DB password/full DSN;
- owner numeric Telegram ID;
- session contents;
- Telegram login/2FA codes;
- live message bodies;
- AI provider keys.
