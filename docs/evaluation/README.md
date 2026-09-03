# Matching Evaluation

This directory stores deterministic offline matching evaluation artifacts.

Run the frozen corpus evaluator with:

```bash
python -m freelancer_bot.matching_evaluation --baseline current-main
```

The JSON report contains:

- `frozen_baseline_metrics`: metrics parsed from
  `docs/evaluation/current_main_matching_baseline.md`.
- `metrics`: metrics for the current worktree implementation.
- `delta_metrics`: current worktree metrics minus the frozen baseline where
  numeric comparison is meaningful.

The committed human-readable baseline is a historical current-main snapshot.
Do not overwrite it with successor metrics. If the command below is used, it
writes the frozen baseline metrics from the report, not successor metrics:

```bash
python -m freelancer_bot.matching_evaluation --baseline current-main --write-baseline
```

The evaluator reads `evaluation/matching_ontology.v1.json`,
`evaluation/matching_corpus.v1.jsonl`, and
`evaluation/matching_corpus.v1.sha256`. It uses the existing deterministic
matching pipeline and local hash embedding provider only. It does not use
Telegram, OpenRouter, external AI, network calls, a database, or production
runtime.

## Final Decision Metrics

`MATCHING_BEHAVIOR_BASE_SHA` identifies the frozen production matching code
baseline used for comparison. Successor PRs report current worktree behavior
separately from that historical baseline.

`DELIVERY_POSITIVE_BUCKET=STRONG_MATCH` is the final decision contract:

`FINAL_TRUE_POSITIVE_COUNT` =
STRONG_MATCH cases reaching final match.

`FINAL_FALSE_POSITIVE_COUNT` =
WEAK_BUT_VALID_CANDIDATE, NON_MATCH, or HARD_CONSTRAINT_REJECT cases reaching
final match.

`FINAL_FALSE_NEGATIVE_COUNT` =
STRONG_MATCH cases that do not reach final match.

`FINAL_MATCH_PRECISION` =
STRONG_MATCH reaching final match / all cases reaching final match.

`FINAL_MATCH_RECALL` =
STRONG_MATCH reaching final match / all STRONG_MATCH cases.

`WEAK_VALID_SURVIVAL_RECALL` and `CANDIDATE_SURVIVAL_RECALL` are retrieval
survival metrics. They do not make WEAK_BUT_VALID_CANDIDATE a final delivery
positive class.

`NO_STRUCTURED_TARGET_OVERLAP_DIAGNOSTIC_COUNT` records the old target-overlap
signal as a diagnostic. It does not define a universal hard reject in the
matching successor.

## Evidence Contract

Each machine-readable case result includes:

`expected_evidence` =
curated ground truth for capability, action/problem, platform, technology,
constraint, and candidate survival expectations.

`actual_evidence_or_observable_proxy` =
the terminal observables plus deterministic successor evidence for capability,
action/problem, platform, technology, and hard-constraint conflicts.

`evidence_contract_status` =
`EXPOSED_BY_MATCHING_SUCCESSOR` when current worktree matching exposes
comparable deterministic evidence signals.
