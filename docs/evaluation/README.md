# Matching Evaluation

This directory stores deterministic offline matching evaluation artifacts.

Run the frozen current-main baseline evaluator with:

```bash
python -m freelancer_bot.matching_evaluation --baseline current-main
```

To regenerate the committed human-readable baseline report:

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
baseline under evaluation. Evaluation-only PR commits must not be read as a
runtime matching behavior change.

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

## Evidence Contract

Each machine-readable case result includes:

`expected_evidence` =
curated ground truth for capability, action/problem, platform, technology,
constraint, and candidate survival expectations.

`actual_evidence_or_observable_proxy` =
the terminal current-main observables available today, plus
`NOT_EXPOSED_BY_CURRENT_MAIN` for semantic evidence dimensions current main does
not expose.

`evidence_contract_status` =
`EXPECTED_ONLY_ACTUAL_NOT_EXPOSED_BY_CURRENT_MAIN` until a later matching
successor exposes comparable semantic evidence signals.
