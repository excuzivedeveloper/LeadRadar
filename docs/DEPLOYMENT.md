# LeadRadar — Current Deployment

**Status:** CANONICAL  
**Snapshot date:** 2026-09-10  
**Deployment code baseline:** `1299e64f28886dffe3b4bb0ddc201952aa8a2a28`  
**Repository/server head:** `1299e64f28886dffe3b4bb0ddc201952aa8a2a28`

This document records the current shared-server LeadRadar layout and deployment boundaries. Exact operational commands live in [`OPERATIONS.md`](OPERATIONS.md).

## Server layout

```text
checkout=/opt/leadradar/LeadRadar
runtime_env=/opt/leadradar/runtime/.env
runtime_sessions=/opt/leadradar/runtime/sessions/
venv=/opt/leadradar/LeadRadar/.venv
python=3.14.7
production_python=./.venv/bin/python
```

Do not modify shared-host global Python for LeadRadar work.

## PostgreSQL

Verified production topology:

```text
container=leadradar-postgres
image=postgres:18.4-alpine
host_bind=127.0.0.1:55432->5432/tcp
health=healthy
alembic_current=20260908_0042
```

The canonical runtime env must be loaded before DB-connected Alembic commands. Never print PostgreSQL credentials or the full credentialed `DATABASE_URL`.

## SearXNG

Verified production topology:

```text
endpoint=http://127.0.0.1:8888
container=freelancer-lead-bot-searxng-1
image_id_prefix=892cf8093419
pinned_image=searxng/searxng@sha256:892cf809341915a4b7710d3c9045005b4c377d51335a089b6d4da0b28750788d
host_bind=127.0.0.1:8888->8080/tcp
host_settings=config/searxng/settings.yml
container_settings=/etc/searxng/settings.yml
settings_mount=read-only
runtime_interpreter=/usr/local/searxng/.venv/bin/python3
state=running
```

Current verified engine strategy:

```yaml
use_default_settings: true

engines:
  - name: brave
    disabled: true
  - name: duckduckgo
    disabled: true
  - name: startpage
    disabled: true
```

This preserves inherited network aliases. Do not replace it with destructive engine removal or `inactive: true`.

## Shared-host no-touch neighbor

Vaultwarden owns host port 8080:

```text
container=vaultwarden
image=vaultwarden/server:latest
host_bind=127.0.0.1:8080->80/tcp
health=healthy
```

LeadRadar SearXNG therefore remains on loopback port 8888. LeadRadar tasks must not modify Vaultwarden.

## Runtime state

There is currently no persistent LeadRadar application runtime.

Expected outside explicitly authorized bounded tasks:

```text
application_process=not running
collector=not running
bot=not running
persistent_runtime_authorized=NO
```

No persistent runtime should be started implicitly by a SearXNG, documentation, database-read, or bounded Web-discovery task.

## Current safety flags

Verified production values:

```text
SOURCE_DISCOVERY_ENABLED=false
SOURCE_AUDIT_ENABLED=false
TELEGRAM_GLOBAL_DISCOVERY_ENABLED=false
SOURCE_GRAPH_DISCOVERY_ENABLED=false
AI_REPLY_ENABLED=false
SEARXNG_PORT=8888
SEARXNG_URL=http://127.0.0.1:8888
DATABASE_URL=configured
```

These values are production state, not `.env.example` completeness claims.

## Telegram identities and sessions

Runtime session directory:

```text
/opt/leadradar/runtime/sessions/
```

Accepted identity separation:

```text
dedicated Telegram account -> collector
owner main Telegram account -> bot user/recipient
Telegram bot -> separate bot identity
```

Session files are bearer credentials. Never print or copy session contents. Two LeadRadar processes must not use the same session concurrently.

The owner-only bot allowlist remains part of the deployment boundary; the numeric owner Telegram ID must not be recorded in canonical docs or reports.

## Source catalog and lifecycle

Repository seed remains configuration/diagnostic input. PostgreSQL is the runtime lifecycle authority.

Verified lifecycle field:

```text
sources.lifecycle_status
candidate_value=candidate
```

Current read-only inventory snapshot:

```text
SOURCE_COUNT=22
CANDIDATE_COUNT=7
OWNER_NOTIFICATION_COUNT=3
```

These counts will naturally change; the schema field names and lifecycle semantics are the contract.

## Current PR24 state

```text
PR24_MERGED=YES
PR24_PRODUCTION_SYNCED=YES
PR24_POST_SYNC_VERIFICATION=PASS
PR24_STAGE_A_OFFLINE=PASS
PR24_LIVE_YIELD_IMPROVEMENT_PROVEN=NO
```

The first attempted PR24 live canary did not reach Web Discovery because the application CLI namespace was invoked instead of the operator CLI namespace. That failure is not evidence about SearXNG/provider performance or PR24 search quality.

The verified operator entrypoint for the next profile Web run is documented in `OPERATIONS.md`.

## Promotion rules

Before production checkout changes:

1. verify exact current HEAD;
2. verify tracked worktree clean;
3. fetch exact authorized target;
4. verify provenance and diff;
5. require fast-forward only;
6. verify exact HEAD after sync;
7. preserve `/opt/leadradar/runtime`;
8. keep activation/restart as a separate authorization unless explicitly included.

Do not sync to a newer-than-authorized `origin/main` and do not use local merge/rebase/destructive reset.

## Shared-server boundary

LeadRadar tasks must not modify:

- WayFound;
- Hermes;
- Vaultwarden;
- unrelated Docker containers, networks or volumes;
- unrelated systemd services;
- firewall;
- system time/NTP;
- global Python;
- unrelated databases.

## Secrets/reporting rules

Safe reports may include commit SHAs, migration revisions, counts, booleans, public container names, non-secret hashes and public source handles.

Reports must not contain bot tokens, API hashes, DB credentials/full DSNs, owner numeric Telegram ID, session contents, Telegram login/2FA codes, live message bodies or AI provider keys.
