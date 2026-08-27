# LeadRadar — Cost and External-Work Safety

**Status:** CANONICAL  
**Last verified:** 2026-08-27

## Current deployment rule

The current deployment is still before the AI gate.

Expected:

```text
AI_REPLY_ENABLED=false
OPENAI_API_KEY_CONFIGURED=NO
DEEPSEEK_API_KEY_CONFIGURED=NO
TOKENROUTER_API_KEY_CONFIGURED=NO

SEND_CATCH_UP=false
SOURCE_DISCOVERY_ENABLED=false
SOURCE_AUDIT_ENABLED=false
SOURCE_GRAPH_DISCOVERY_ENABLED=false
TELEGRAM_CHAT_DISCOVERY_ENABLED=false

PERSISTENT_RUNTIME_AUTHORIZED=NO
```

Do not enable AI, discovery or catch-up merely because supporting code already
exists.

The active order is defined in `docs/ACTIVE_PLAN.md`.

## Fresh-clone defaults

A fresh clone has no credentials and the no-argument CLI exits after printing
help. CI must not run live Telegram, provider, discovery, audit or payment calls.

Relevant conservative defaults include:

- `AI_REPLY_ENABLED=false`
- `SEND_CATCH_UP=false`
- `LEGACY_DELIVERY_ENABLED=false`
- `SOURCE_DISCOVERY_ENABLED=false`
- `SOURCE_AUDIT_ENABLED=false`
- `SOURCE_GRAPH_DISCOVERY_ENABLED=false`
- `TELEGRAM_CHAT_DISCOVERY_ENABLED=false`
- Opportunity fallback disabled
- bounded output/transport attempts
- Opportunity analysis daily/monthly spend guards

These defaults are safety controls, not a guarantee against spend after an
operator changes configuration.

## Before enabling AI

Only after the live shadow-evidence gate passes:

1. choose an exact supported provider and model;
2. use a dedicated BYOK key;
3. set a low provider-side spend/rate limit;
4. verify model pricing and configure repository pricing inputs where required;
5. keep fallback disabled for the first bounded canary;
6. preserve the repository daily/monthly spend guards;
7. use a small fresh-message window;
8. inspect AI telemetry and job counts before increasing limits.

Do not enable discovery in the same first AI canary.

Missing keys should fail closed. Never recover a key from a chat transcript.

## Before enabling catch-up

Current canaries intentionally use natural new traffic.

Do not set `SEND_CATCH_UP=true` simply because no live message arrived during a
short observation window.

Catch-up changes load/history semantics and must be a separately authorized
test with explicit per-source/global bounds.

## Before enabling discovery/audit

Discovery and audit can create Telegram/Web request load independently of normal
passive collection.

Before enabling:

- preserve Telegram request governor pacing/cooldowns;
- choose a bounded source/sample scope;
- configure only the required Web/AI provider;
- verify access/lifecycle rules;
- cap audits/candidates/history;
- observe FloodWait/rate-limit behavior.

A missing Web provider is an unavailable optional capability, not a signal for
continuous retries.

## Owner-only delivery safety

Current private deployment has one allowlisted owner.

Do not enable a delivery stage until the recipient allowlist is verified
effective. Non-allowlisted personalized delivery must be suppressed before
Telegram send.

## Persistent runtime

Persistent execution can accumulate Telegram/provider work continuously.

Do not create or enable a daemon until bounded ingestion, AI and owner-delivery
stages pass and a restart/log/resource policy is explicitly approved.

## CI invariant

GitHub Actions should contain no real provider credentials and should exercise
deterministic/fake-provider paths only.
