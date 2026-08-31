# LeadRadar — Cost and External-Work Safety

**Status:** CANONICAL  
**Last verified:** 2026-08-31

## Current deployment rule

The current deployment is pre-live-AI. OpenRouter Opportunity Analysis support
is implemented and server-synced, and the selected OpenRouter runtime route is
configured. No live provider call has occurred.

Expected:

```text
AI_REPLY_ENABLED=false
OPENAI_API_KEY_CONFIGURED=NO
DEEPSEEK_API_KEY_CONFIGURED=NO
TOKENROUTER_API_KEY_CONFIGURED=NO
OPENROUTER_API_KEY_CONFIGURED=YES
OPPORTUNITY_ANALYSIS_PROVIDER=openrouter
OPPORTUNITY_ANALYSIS_MODEL=minimax/minimax-m3:free
PROVIDER_LIVE_CALLS=0
READY_FOR_OPENROUTER_CONFIGURATION=COMPLETE
READY_FOR_BOUNDED_AI_ANALYSIS=YES

SEND_CATCH_UP=false
SOURCE_DISCOVERY_ENABLED=false
SOURCE_AUDIT_ENABLED=false
SOURCE_GRAPH_DISCOVERY_ENABLED=false
TELEGRAM_CHAT_DISCOVERY_ENABLED=false

PERSISTENT_RUNTIME_AUTHORIZED=NO
```

Do not enable provider calls, discovery or catch-up merely because supporting
code already exists.

The active order is defined in `docs/ACTIVE_PLAN.md`.

Critical runtime invariant:

```text
matching Opportunity Analysis provider key present
+ full python -m freelancer_bot --run
=> opportunity.analysis.v1 jobs can be processed
=> provider calls can occur
```

There is no separate `OPPORTUNITY_ANALYSIS_ENABLED` switch. `AI_REPLY_ENABLED`
gates reply drafting only and does not disable Opportunity Analysis. The
the first live AI canary must use the bounded one-shot job command rather than
full runtime.

For the first canary, use:

```bash
python -m freelancer_bot --opportunity-analysis-job-id <UUID>
```

The command requires an explicit `opportunity.analysis.v1` durable job UUID,
processes at most that selected job once, and exits without claiming a second
job. With `OPPORTUNITY_ANALYSIS_MAX_OUTPUT_ATTEMPTS=1` and
`OPPORTUNITY_ANALYSIS_FALLBACK_ENABLED=false`, one invocation can make at most
one provider request.

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

## Before the first live Opportunity Analysis call

The selected first route is OpenRouter with `minimax/minimax-m3:free`.

Before the first live call:

1. reverify current model availability and pricing from authoritative provider
   information;
2. keep using the dedicated BYOK OpenRouter key without printing it;
3. verify low provider-side spend/rate limits where available;
4. keep repository pricing inputs aligned with operator-verified values;
5. keep fallback disabled;
6. preserve repository daily/monthly spend guards;
7. use only the explicit one-shot provider-call/job mechanism;
8. inspect AI telemetry and job counts before increasing limits.

Do not enable discovery in the same first AI canary.

Missing keys should fail closed. Never recover a key from a chat transcript.

Current external information may report `minimax/minimax-m3:free` input/output
pricing as free, but that is not a provider-side cost guarantee. A local
configured price of `0/0` is descriptive telemetry/accounting, not proof that
external billing, rate limits or free-tier availability cannot change.

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
