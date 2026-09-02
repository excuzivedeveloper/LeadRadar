from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from .match_decisions import (
    MatchDecisionCode,
    MatchDecisionPolicy,
    MatchScoringInput,
    decide_and_rank_matches,
)
from .opportunity_analysis import OpportunityAnalysis
from .persistence.opportunities import (
    CANONICAL_OPPORTUNITY_SCHEMA_VERSION,
    CanonicalOpportunityRecord,
    OpportunityLifecycleStatus,
)
from .persistence.search_profiles import (
    SearchProfileConfirmationStatus,
    SearchProfileRecord,
)
from .search_profiles import (
    BudgetPolicy,
    OpportunityType,
    WorkMode,
    parse_search_profile,
    parse_search_profile_preferences,
)
from .semantic_matching import (
    DeterministicHashEmbeddingProvider,
    score_candidates_semantic,
)


ONTOLOGY_VERSION = "ontology.v1"
CORPUS_SCHEMA_VERSION = "matching-evaluation-corpus.v1"
EVALUATOR_VERSION = "matching-evaluator.v1"
DEFAULT_ONTOLOGY_PATH = Path("evaluation/matching_ontology.v1.json")
DEFAULT_CORPUS_PATH = Path("evaluation/matching_corpus.v1.jsonl")
DEFAULT_CORPUS_SHA_PATH = Path("evaluation/matching_corpus.v1.sha256")
DEFAULT_BASELINE_PATH = Path("docs/evaluation/current_main_matching_baseline.md")
BASELINE_CODE_SHA = "4b53cbc710739a55ff88d0476ad14aafe78e4944"
EVALUATED_AT = datetime(2026, 9, 2, 0, 0, tzinfo=timezone.utc)

CAPABILITY_FAMILIES = frozenset(
    {
        "api_webhook_integrations",
        "android_kotlin_utility",
        "browser_automation",
        "business_automation",
        "chrome_extension",
        "docker_vps_deployment",
        "fullstack_product_integration",
        "google_sheets_automation",
        "llm_ai_integration",
        "monitoring_alerting",
        "python_backend_api",
        "react_next_web",
        "responsive_frontend",
        "telegram_automation",
        "web_scraping",
    }
)


class ExpectedBucket(str, Enum):
    STRONG_MATCH = "STRONG_MATCH"
    WEAK_BUT_VALID_CANDIDATE = "WEAK_BUT_VALID_CANDIDATE"
    NON_MATCH = "NON_MATCH"
    HARD_CONSTRAINT_REJECT = "HARD_CONSTRAINT_REJECT"


class EvidenceExpectation(str, Enum):
    YES = "YES"
    NO = "NO"
    UNKNOWN = "UNKNOWN"


class EvaluationInputError(ValueError):
    pass


@dataclass(frozen=True)
class EvaluationCase:
    raw: dict[str, Any]

    @property
    def case_id(self) -> str:
        return self.raw["case_id"]

    @property
    def expected_bucket(self) -> ExpectedBucket:
        return ExpectedBucket(self.raw["expected_bucket"])

    @property
    def expected_candidate_should_survive(self) -> EvidenceExpectation:
        return EvidenceExpectation(self.raw["expected_candidate_should_survive"])

    @property
    def adversarial_or_negative(self) -> bool:
        return bool(self.raw["adversarial_or_negative"])


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    expected_bucket: str
    final_stage: str
    candidate_survived: bool
    final_match: bool
    decision_code: str
    hard_filter_reasons: tuple[str, ...]
    combined_relevance_score: str | None
    final_rank_score: str | None


@dataclass(frozen=True)
class EvaluationReport:
    metrics: dict[str, Any]
    cases: tuple[CaseResult, ...]
    corpus_sha256: str


def load_ontology(path: Path = DEFAULT_ONTOLOGY_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvaluationInputError(f"ontology file not found: {path}") from exc
    if payload.get("ontology_version") != ONTOLOGY_VERSION:
        raise EvaluationInputError("ontology version mismatch")
    families = set(payload.get("capability_families", []))
    if families != CAPABILITY_FAMILIES:
        raise EvaluationInputError("ontology capability families mismatch")
    return payload


def load_corpus(
    path: Path = DEFAULT_CORPUS_PATH,
    *,
    ontology: dict[str, Any] | None = None,
) -> tuple[EvaluationCase, ...]:
    selected_ontology = ontology or load_ontology()
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    cases = tuple(
        EvaluationCase(json.loads(line))
        for line in raw_lines
        if line.strip()
    )
    validate_corpus(cases, ontology=selected_ontology)
    return cases


def corpus_sha256(path: Path = DEFAULT_CORPUS_PATH) -> str:
    normalized = "\n".join(path.read_text(encoding="utf-8").splitlines()) + "\n"
    return sha256(normalized.encode("utf-8")).hexdigest()


def validate_recorded_corpus_sha(
    corpus_path: Path = DEFAULT_CORPUS_PATH,
    sha_path: Path = DEFAULT_CORPUS_SHA_PATH,
) -> str:
    actual = corpus_sha256(corpus_path)
    recorded = sha_path.read_text(encoding="utf-8").strip()
    if actual != recorded:
        raise EvaluationInputError(
            f"corpus sha256 mismatch: expected {recorded}, actual {actual}"
        )
    return actual


def validate_corpus(
    cases: tuple[EvaluationCase, ...],
    *,
    ontology: dict[str, Any],
) -> None:
    if len(cases) < 160:
        raise EvaluationInputError("corpus must contain at least 160 cases")
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise EvaluationInputError("case IDs must be unique")

    capabilities = set(ontology["capability_families"])
    languages = Counter()
    buckets = Counter()
    adversarial_or_negative = 0
    for case in cases:
        raw = case.raw
        _require(raw, "case_id", str)
        if _require(raw, "schema_version", str) != CORPUS_SCHEMA_VERSION:
            raise EvaluationInputError(f"{case.case_id}: corpus schema mismatch")
        if _require(raw, "ontology_version", str) != ONTOLOGY_VERSION:
            raise EvaluationInputError(f"{case.case_id}: ontology version mismatch")
        _require(raw, "language", str)
        _require(raw, "adversarial_or_negative", bool)
        _require(raw, "ontology", dict)
        _require(raw, "opportunity", dict)
        _require(raw, "profile", dict)
        for field in (
            "expected_capability_match",
            "expected_action_problem_match",
            "expected_platform_match",
            "expected_technology_match",
            "expected_hard_constraint_conflict",
            "expected_candidate_should_survive",
        ):
            EvidenceExpectation(_require(raw, field, str))
        bucket = case.expected_bucket
        languages[raw["language"]] += 1
        buckets[bucket.value] += 1
        adversarial_or_negative += int(case.adversarial_or_negative)
        for capability in raw["ontology"].get("capability", []):
            if capability not in capabilities:
                raise EvaluationInputError(
                    f"{case.case_id}: unknown capability {capability}"
                )

    if languages["RU"] < 55 or languages["EN"] < 40 or languages["MIXED"] < 30:
        raise EvaluationInputError("language coverage floor is not met")
    for bucket in ExpectedBucket:
        if not buckets[bucket.value]:
            raise EvaluationInputError(f"missing expected bucket {bucket.value}")
    if adversarial_or_negative < 60:
        raise EvaluationInputError("adversarial/negative coverage floor is not met")


def evaluate_current_main(
    cases: tuple[EvaluationCase, ...],
    *,
    corpus_digest: str,
) -> EvaluationReport:
    results = tuple(_evaluate_case(case) for case in cases)
    buckets = Counter(case.expected_bucket.value for case in cases)
    language_counts = Counter(case.raw["language"] for case in cases)

    strong = [result for result in results if result.expected_bucket == "STRONG_MATCH"]
    weak = [
        result
        for result in results
        if result.expected_bucket == "WEAK_BUT_VALID_CANDIDATE"
    ]
    non_match = [result for result in results if result.expected_bucket == "NON_MATCH"]
    hard_reject = [
        result
        for result in results
        if result.expected_bucket == "HARD_CONSTRAINT_REJECT"
    ]
    should_survive = [
        result
        for case, result in zip(cases, results, strict=True)
        if case.expected_candidate_should_survive is EvidenceExpectation.YES
    ]
    final_positive = [
        result
        for result in results
        if result.expected_bucket in {"STRONG_MATCH", "WEAK_BUT_VALID_CANDIDATE"}
    ]
    final_matches = [result for result in results if result.final_match]
    true_final_matches = [
        result for result in final_matches if result.expected_bucket == "STRONG_MATCH"
    ]
    false_positives = [
        result
        for result in final_matches
        if result.expected_bucket in {"NON_MATCH", "HARD_CONSTRAINT_REJECT"}
    ]
    false_negatives = [
        result for result in strong if not result.final_match
    ]

    metrics = {
        "BASELINE_CODE_SHA": BASELINE_CODE_SHA,
        "ONTOLOGY_VERSION": ONTOLOGY_VERSION,
        "CORPUS_SCHEMA_VERSION": CORPUS_SCHEMA_VERSION,
        "CORPUS_SHA256": corpus_digest,
        "TOTAL_CASES": len(cases),
        "RU_CASES": language_counts["RU"],
        "EN_CASES": language_counts["EN"],
        "MIXED_CASES": language_counts["MIXED"],
        "ADVERSARIAL_OR_NEGATIVE_CASES": sum(
            int(case.adversarial_or_negative) for case in cases
        ),
        "STRONG_MATCH_CASES": buckets["STRONG_MATCH"],
        "WEAK_BUT_VALID_CASES": buckets["WEAK_BUT_VALID_CANDIDATE"],
        "NON_MATCH_CASES": buckets["NON_MATCH"],
        "HARD_CONSTRAINT_REJECT_CASES": buckets["HARD_CONSTRAINT_REJECT"],
        "CANDIDATE_SURVIVAL_RECALL": _ratio(
            sum(result.candidate_survived for result in should_survive),
            len(should_survive),
        ),
        "STRONG_MATCH_SURVIVAL_RECALL": _ratio(
            sum(result.candidate_survived for result in strong),
            len(strong),
        ),
        "WEAK_VALID_SURVIVAL_RECALL": _ratio(
            sum(result.candidate_survived for result in weak),
            len(weak),
        ),
        "NON_MATCH_SURVIVAL_RATE": _ratio(
            sum(result.candidate_survived for result in non_match),
            len(non_match),
        ),
        "HARD_CONSTRAINT_REJECT_ACCURACY": _ratio(
            sum(
                result.decision_code == MatchDecisionCode.HARD_REJECTED.value
                and any(
                    not reason.startswith("narrowing.")
                    for reason in result.hard_filter_reasons
                )
                for result in hard_reject
            ),
            len(hard_reject),
        ),
        "DELIVERY_OR_FINAL_MATCH_PRECISION": _ratio(
            len(true_final_matches),
            len(final_matches),
        ),
        "DELIVERY_OR_FINAL_MATCH_RECALL": _ratio(
            sum(result.final_match for result in strong),
            len(strong),
        ),
        "FALSE_POSITIVE_COUNT": len(false_positives),
        "FALSE_NEGATIVE_COUNT": len(false_negatives),
        "NO_STRUCTURED_TARGET_OVERLAP_COUNT": sum(
            "narrowing.no_structured_target_overlap" in result.hard_filter_reasons
            for result in results
        ),
        "BELOW_RELEVANCE_THRESHOLD_COUNT": sum(
            result.decision_code
            == MatchDecisionCode.BELOW_RELEVANCE_THRESHOLD.value
            for result in results
        ),
        "BELOW_RANK_SCORE_THRESHOLD_COUNT": sum(
            result.decision_code
            == MatchDecisionCode.BELOW_RANK_SCORE_THRESHOLD.value
            for result in results
        ),
    }
    return EvaluationReport(metrics=metrics, cases=results, corpus_sha256=corpus_digest)


def write_baseline_report(report: EvaluationReport, path: Path) -> None:
    lines = [
        "# LeadRadar Matching Evaluation Baseline",
        "",
        "Generated by:",
        "",
        "```bash",
        "python -m freelancer_bot.matching_evaluation --baseline current-main --write-baseline",
        "```",
        "",
        "This records deterministic offline behavior only. It does not use Telegram,",
        "OpenRouter, external AI, network calls, a database, or production runtime.",
        "",
        "## Metrics",
        "",
    ]
    for key, value in report.metrics.items():
        lines.append(f"{key}={value}")
    lines.extend(
        [
            "",
            "## Terminal Decision",
            "",
            "The closest deterministic offline terminal decision is",
            "`MatchDecisionCode.ELIGIBLE` from `decide_and_rank_matches()`. It is",
            "reported as `DELIVERY_OR_FINAL_MATCH_*` because this evaluator does",
            "not execute personalized Telegram delivery.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def report_as_json(report: EvaluationReport) -> dict[str, Any]:
    return {
        "schema_version": "matching-evaluation-report.v1",
        "evaluator_version": EVALUATOR_VERSION,
        "metrics": report.metrics,
        "cases": [case.__dict__ for case in report.cases],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate frozen matching corpus.")
    parser.add_argument("--baseline", choices=("current-main",), required=True)
    parser.add_argument("--ontology", type=Path, default=DEFAULT_ONTOLOGY_PATH)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--corpus-sha", type=Path, default=DEFAULT_CORPUS_SHA_PATH)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--baseline-output", type=Path, default=DEFAULT_BASELINE_PATH)
    args = parser.parse_args(argv)

    ontology = load_ontology(args.ontology)
    cases = load_corpus(args.corpus, ontology=ontology)
    digest = validate_recorded_corpus_sha(args.corpus, args.corpus_sha)
    report = evaluate_current_main(cases, corpus_digest=digest)
    output = report_as_json(report)
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2))
    if args.json is not None:
        args.json.write_text(
            json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.write_baseline:
        write_baseline_report(report, args.baseline_output)
    return 0


def _evaluate_case(case: EvaluationCase) -> CaseResult:
    opportunity = _opportunity(case)
    profile = _profile(case)
    semantic = score_candidates_semantic(
        opportunity,
        (profile,),
        provider=DeterministicHashEmbeddingProvider(),
    )
    trace = decide_and_rank_matches(
        (MatchScoringInput(opportunity, (profile,), semantic),),
        evaluated_at=EVALUATED_AT,
        policy=MatchDecisionPolicy(),
    ).traces[0]
    hard_reasons = tuple(reason["code"] for reason in trace.hard_filter_reasons)
    if not trace.hard_filter_eligible:
        final_stage = (
            "narrowing.no_structured_target_overlap"
            if "narrowing.no_structured_target_overlap" in hard_reasons
            else "hard_filter"
        )
    else:
        final_stage = trace.decision_code.value
    return CaseResult(
        case_id=case.case_id,
        expected_bucket=case.expected_bucket.value,
        final_stage=final_stage,
        candidate_survived=trace.hard_filter_eligible,
        final_match=trace.eligible,
        decision_code=trace.decision_code.value,
        hard_filter_reasons=hard_reasons,
        combined_relevance_score=(
            None
            if trace.combined_relevance_score is None
            else str(trace.combined_relevance_score)
        ),
        final_rank_score=(
            None if trace.final_rank_score is None else str(trace.final_rank_score)
        ),
    )


def _opportunity(case: EvaluationCase) -> CanonicalOpportunityRecord:
    raw = case.raw["opportunity"]
    analysis_payload = {
            "schema_version": "opportunity_analysis.v1",
            "is_opportunity": True,
            "confidence": float(raw.get("confidence", "0.9")),
            "market_direction": "buyer_to_specialist",
            "intent_stage": "active",
            "opportunity_type": raw.get("opportunity_type", "project"),
            "category": raw.get("category"),
            "role_title": raw.get("role_title"),
            "skills": raw.get("skills", []),
            "task_summary": raw.get("task_summary", ""),
            "budget": raw.get(
                "budget",
                {
                    "known": False,
                    "min": None,
                    "max": None,
                    "currency": None,
                    "period": None,
                    "explicit": False,
                },
            ),
            "work": {
                "remote": raw.get("remote"),
                "location": raw.get("location"),
                "full_time": None,
                "part_time": None,
            },
            "language": raw.get("language"),
            "contact": {"telegram": None, "email": None, "url": None},
            "quality": {
                "actionability": float(raw.get("quality", "0.8")),
                "commercial_plausibility": float(raw.get("quality", "0.8")),
                "specificity": float(raw.get("quality", "0.8")),
                "credibility": float(raw.get("quality", "0.8")),
            },
            "red_flags": raw.get("red_flags", []),
        }
    analysis = OpportunityAnalysis.model_validate_json(
        json.dumps(analysis_payload, ensure_ascii=False)
    )
    return CanonicalOpportunityRecord(
        id=uuid5(NAMESPACE_URL, f"leadradar:evaluation:opportunity:{case.case_id}"),
        schema_version=CANONICAL_OPPORTUNITY_SCHEMA_VERSION,
        canonical_title=analysis.role_title,
        task_summary=analysis.task_summary,
        analysis=analysis,
        first_seen_at=EVALUATED_AT,
        last_seen_at=EVALUATED_AT,
        lifecycle_status=OpportunityLifecycleStatus.ACTIVE,
        lifecycle_changed_at=EVALUATED_AT,
        raw_message_ids=(),
        analysis_cache_ids=(),
        analysis_links=(),
        preferred_source_policy_version=None,
        preferred_source=None,
        source_observations=(),
        lifecycle_events=(),
        created_at=EVALUATED_AT,
        updated_at=EVALUATED_AT,
    )


def _profile(case: EvaluationCase) -> SearchProfileRecord:
    raw = case.raw["profile"]
    parsed = parse_search_profile(
        roles=tuple(raw.get("roles", [])),
        skills=tuple(raw.get("skills", [])),
        categories=tuple(raw.get("categories", [])),
        semantic_text=raw.get("semantic_text", ""),
    )
    preferences_raw = raw.get("preferences", {})
    preferences = parse_search_profile_preferences(
        work_types=_work_types(preferences_raw.get("work_types")),
        minimum_budget=preferences_raw.get("minimum_budget"),
        currency=preferences_raw.get("currency"),
        budget_policy=_budget_policy(preferences_raw.get("budget_policy")),
        languages=_tuple_or_none(preferences_raw.get("languages")),
        geographies=_tuple_or_none(preferences_raw.get("geographies")),
        work_modes=_work_modes(preferences_raw.get("work_modes")),
        excluded_categories=_tuple_or_none(
            preferences_raw.get("excluded_categories")
        ),
    )
    return SearchProfileRecord(
        id=uuid5(NAMESPACE_URL, f"leadradar:evaluation:profile:{case.case_id}"),
        user_id=uuid5(NAMESPACE_URL, f"leadradar:evaluation:user:{case.case_id}"),
        schema_version=parsed.schema_version,
        parser_version=parsed.parser_version,
        analysis_cache_id=None,
        roles=parsed.roles,
        skills=parsed.skills,
        categories=parsed.categories,
        semantic_text_original=parsed.semantic_text_original,
        semantic_text_normalized=parsed.semantic_text_normalized,
        preferences=preferences,
        confirmation_status=SearchProfileConfirmationStatus.CONFIRMED,
        revision=1,
        confirmed_at=EVALUATED_AT,
        is_active=True,
        is_primary=True,
        activated_at=EVALUATED_AT,
        deactivated_at=None,
        created_at=EVALUATED_AT,
        updated_at=EVALUATED_AT,
    )


def _work_types(values: list[str] | None) -> tuple[OpportunityType, ...] | None:
    if values is None:
        return None
    return tuple(OpportunityType(value) for value in values)


def _work_modes(values: list[str] | None) -> tuple[WorkMode, ...] | None:
    if values is None:
        return None
    return tuple(WorkMode(value) for value in values)


def _budget_policy(value: str | None) -> BudgetPolicy | None:
    return None if value is None else BudgetPolicy(value)


def _tuple_or_none(values: list[str] | None) -> tuple[str, ...] | None:
    return None if values is None else tuple(values)


def _ratio(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0.0000"
    return (Decimal(numerator) / Decimal(denominator)).quantize(
        Decimal("0.0001")
    ).to_eng_string()


def _require(raw: dict[str, Any], field: str, expected_type: type) -> Any:
    if field not in raw:
        raise EvaluationInputError(f"missing required field: {field}")
    value = raw[field]
    if not isinstance(value, expected_type):
        raise EvaluationInputError(f"{field} must be {expected_type.__name__}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
