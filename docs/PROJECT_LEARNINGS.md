# LeadRadar — Project Learnings

**Status:** CANONICAL
**Last verified:** 2026-09-09

This file records operational lessons that should shape future implementation,
review and server work. Read it immediately after `docs/DOCUMENTATION_INDEX.md`.

## Current Lessons

- **Implementation state and production state are separate facts.** A reviewed
  repository change is not production behavior until the exact reviewed commit is
  merged, synced to the server and activated where needed.
- **Canonical docs can lag current `main` or server evidence.** Prefer fresh
  runtime/server evidence first, then current code, then canonical docs. When
  they diverge, update docs in the same workstream instead of treating stale text
  as authority.
- **A one-shot query bound is not a persistent-runtime bound.** The
  `profile-discovery run --max-queries` contract bounds that explicit operator
  invocation only. It does not authorize or bound unattended persistent source
  discovery.
- **Web provider backoff is evidence, not permission to retry.** A degraded
  provider state such as `BACKOFF` documents what happened and should inform the
  next reviewed gate; it is not authorization for an immediate second live run.
- **SearXNG default engine inheritance matters.** `use_default_settings: true`
  inherits default engines even when the local settings file has no explicit
  engine list.
- **Exact SearXNG engine names matter.** Removing `brave`, `duckduckgo` and
  `startpage` targets only those exact general engines. Variants such as
  `brave.images`, `brave.videos`, `brave.news` or `duckduckgo images` are
  separate names and must not be assumed removed.
- **Container runtime must be discovered, not guessed.** The verified SearXNG
  runtime interpreter is `/usr/local/searxng/.venv/bin/python3`; generic
  `docker exec ... python` is not reliable for this runtime environment.
- **Docker exec heredoc diagnostics require stdin attachment.** Use
  `docker exec -i` when passing a heredoc or stdin-driven script into the
  container.
- **Read-only diagnostics do not authorize repair.** Inspecting server state,
  container settings, database rows or provider evidence does not grant
  permission to restart, recreate, write, retry or repair.
- **Failed read-only checkpoints are hard-stop gates.** If an authorized
  read-only continuity or diagnostic checkpoint fails or mismatches, stop
  immediately. Do not improvise repairs, alternate commands or paths, retries,
  or substitute diagnostics unless a new reviewed and authorized task explicitly
  permits them.
- **SearXNG and the LeadRadar persistent runtime are separate services.** A
  SearXNG config/restart gate does not authorize the LeadRadar app/bot/collector
  persistent runtime, and a LeadRadar runtime gate does not imply SearXNG config
  activation.
- **Documentation should preserve exact operational facts.** Record commit SHAs,
  run keys, counts, migration revisions, container names, paths and gate states
  precisely, while still omitting secrets and live message bodies.
