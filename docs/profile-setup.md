# LeadRadar — Profile Setup

**Status:** CURRENT  
**Last verified:** 2026-08-27

LeadRadar currently has two different profile concepts. They serve different
purposes and must not be confused.

## 1. V2 SearchProfile — used for matching

The primary V2 user profile is a PostgreSQL `SearchProfile`.

It represents what a user wants LeadRadar to find and is used by the matching
pipeline.

Multiple SearchProfiles per user are supported with ownership isolation.

The normal UI path starts from the Telegram bot and can create a draft from a
natural-language description, then lets the user confirm/activate it.

### Natural-language onboarding

Natural-language SearchProfile extraction requires a configured onboarding AI
provider.

Relevant configuration includes:

```dotenv
ONBOARDING_PROFILE_PROVIDER=
ONBOARDING_PROFILE_MODEL=
```

and the corresponding provider key.

**Current deployment state:** no AI key is configured yet, so live
natural-language onboarding is not the current stage.

Do not enable it before the AI provider step in `docs/ACTIVE_PLAN.md`.

### Manual profile path

The bot also contains an explicit manual profile path/commands.

This can be used without treating the legacy `freelancer_profile.json` as a V2
SearchProfile.

Any live profile-creation test must still use the owner-only bot boundary and
PostgreSQL repositories.

## 2. Legacy reply profile — `freelancer_profile.json`

`freelancer_profile.example.json` is a separate profile used for reply-drafting
style/context.

Typical fields describe:

- positioning;
- services;
- stack;
- cases;
- tone;
- claims/style restrictions;
- projects to avoid.

Create a local ignored copy only when that legacy reply-generation capability
is being configured:

```bash
cp freelancer_profile.example.json freelancer_profile.json
```

The runtime path is controlled by:

```dotenv
FREELANCER_PROFILE_PATH=freelancer_profile.json
```

This JSON file is **not** the PostgreSQL V2 SearchProfile used by matching.

## 3. Reply generation

`AI_REPLY_ENABLED` controls the optional reply-draft feature.

Current deployment:

```text
AI_REPLY_ENABLED=false
```

Do not turn it on during ingestion/shadow validation.

A future reply-drafting test should be a separate bounded provider/cost task.

## 4. Filters are not the V2 SearchProfile

`config/filters.json` contains the preserved legacy keyword/stop-word logic.

In the current V2 architecture:

- the cheap V2 prefilter is high-recall;
- legacy `match_text()` is recorded in shadow after cheap-prefilter pass;
- the legacy filter does not replace SearchProfile matching.

Do not tune `filters.json` as a substitute for configuring the user's V2
SearchProfile.

## 5. Source catalog is separate from profile configuration

`config/sources.json` seeds candidate/approved sources. Runtime monitoring uses
PostgreSQL source lifecycle/access state.

Changing a user's SearchProfile does not automatically make a source approved.

## 6. Current recommended order for this deployment

Do not create/tune profiles ahead of the current gate.

Current order:

1. obtain live raw + shadow evidence;
2. select/configure AI provider and budget;
3. bounded live Opportunity analysis;
4. validate owner SearchProfile onboarding/manual path;
5. activate an owner profile;
6. bounded matching;
7. bounded personalized delivery to the owner.

See `docs/ACTIVE_PLAN.md`.

## 7. Local deterministic checks

Filter check:

```bash
uv run --frozen python -m freelancer_bot --check-filter \
  "Нужно сделать Telegram-бота с интеграцией API"
```

Configuration validation:

```bash
uv run --frozen python -m freelancer_bot --check-config
```

Source accessibility checks are networked and must use an explicitly authorized
Telegram session/task.

## 8. Security

Never put:

- Telegram IDs;
- bot token/API hash;
- provider keys;
- DB credentials;
- private customer data;

inside profile JSON or repository documentation.
