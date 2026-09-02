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
