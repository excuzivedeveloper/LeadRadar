from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from freelancer_bot.matching_evaluation import (
    CAPABILITY_FAMILIES,
    DEFAULT_BASELINE_PATH,
    DEFAULT_CORPUS_PATH,
    DEFAULT_CORPUS_SHA_PATH,
    ExpectedBucket,
    corpus_sha256,
    evaluate_current_main,
    load_corpus,
    load_ontology,
    report_as_json,
    validate_recorded_corpus_sha,
)


class MatchingEvaluationCorpusTest(unittest.TestCase):
    def test_corpus_schema_unique_ids_and_recorded_digest_are_stable(self):
        ontology = load_ontology()
        cases = load_corpus(ontology=ontology)

        self.assertEqual(len(cases), 200)
        self.assertEqual(
            validate_recorded_corpus_sha(),
            DEFAULT_CORPUS_SHA_PATH.read_text(encoding="utf-8").strip(),
        )
        self.assertEqual(
            corpus_sha256(DEFAULT_CORPUS_PATH),
            "a882b83ebee96e8d8c6a2239b5c679b2047116b84e885a9de5eedc23ab78916c",
        )
        self.assertEqual(len({case.case_id for case in cases}), len(cases))

    def test_ontology_references_are_valid_and_dimensions_are_decomposed(self):
        ontology = load_ontology()
        cases = load_corpus(ontology=ontology)
        dimensions = set(ontology["evidence_dimensions"])

        self.assertEqual(set(ontology["capability_families"]), CAPABILITY_FAMILIES)
        self.assertEqual(
            dimensions,
            {"capability", "action_or_problem", "platform", "technology", "constraint"},
        )
        for case in cases:
            self.assertEqual(case.raw["schema_version"], "matching-evaluation-corpus.v1")
            self.assertEqual(case.raw["ontology_version"], "ontology.v1")
            self.assertTrue(set(case.raw["ontology"]).issubset(dimensions))
            for capability in case.raw["ontology"]["capability"]:
                self.assertIn(capability, CAPABILITY_FAMILIES)

    def test_language_bucket_and_adversarial_floors_are_met(self):
        cases = load_corpus()
        languages = {
            language: sum(case.raw["language"] == language for case in cases)
            for language in ("RU", "EN", "MIXED")
        }

        self.assertGreaterEqual(languages["RU"], 55)
        self.assertGreaterEqual(languages["EN"], 40)
        self.assertGreaterEqual(languages["MIXED"], 30)
        self.assertGreaterEqual(
            sum(case.adversarial_or_negative for case in cases),
            60,
        )

    def test_all_expected_buckets_and_evidence_fields_are_present(self):
        cases = load_corpus()
        buckets = {case.expected_bucket for case in cases}

        self.assertEqual(buckets, set(ExpectedBucket))
        for case in cases:
            for field in (
                "expected_capability_match",
                "expected_action_problem_match",
                "expected_platform_match",
                "expected_technology_match",
                "expected_hard_constraint_conflict",
                "expected_candidate_should_survive",
            ):
                self.assertIn(case.raw[field], {"YES", "NO", "UNKNOWN"})

    def test_representative_adversarial_dimensions_are_semantic(self):
        cases = {case.case_id: case.raw for case in load_corpus()}

        expected = {
            "ru_adversarial_001_website_chatbot_vs_telegram_bot": {
                "expected_capability_match": "YES",
                "expected_action_problem_match": "YES",
                "expected_platform_match": "NO",
                "expected_technology_match": "UNKNOWN",
                "expected_candidate_should_survive": "YES",
            },
            "en_adversarial_002_whatsapp_bot_vs_telegram_workflow": {
                "expected_capability_match": "YES",
                "expected_action_problem_match": "YES",
                "expected_platform_match": "NO",
                "expected_technology_match": "UNKNOWN",
                "expected_candidate_should_survive": "YES",
            },
            "en_adversarial_005_react_native_vs_nextjs": {
                "expected_capability_match": "YES",
                "expected_action_problem_match": "YES",
                "expected_platform_match": "NO",
                "expected_technology_match": "NO",
                "expected_candidate_should_survive": "YES",
            },
            "mixed_adversarial_007_generic_backend_vs_fastapi": {
                "expected_capability_match": "YES",
                "expected_action_problem_match": "YES",
                "expected_platform_match": "UNKNOWN",
                "expected_technology_match": "UNKNOWN",
                "expected_candidate_should_survive": "YES",
            },
            "mixed_adversarial_010_prompt_writing_vs_llm_api": {
                "expected_capability_match": "YES",
                "expected_action_problem_match": "NO",
                "expected_platform_match": "UNKNOWN",
                "expected_technology_match": "UNKNOWN",
                "expected_candidate_should_survive": "YES",
            },
            "mixed_adversarial_013_xml_parser_vs_browser_automation": {
                "expected_capability_match": "YES",
                "expected_action_problem_match": "YES",
                "expected_platform_match": "UNKNOWN",
                "expected_technology_match": "NO",
                "expected_candidate_should_survive": "YES",
            },
            "mixed_adversarial_016_bot_moderation_vs_bot_development": {
                "expected_capability_match": "YES",
                "expected_action_problem_match": "NO",
                "expected_platform_match": "YES",
                "expected_technology_match": "UNKNOWN",
                "expected_candidate_should_survive": "YES",
            },
            "ru_adversarial_021_python_tutor_vs_python_contractor": {
                "expected_capability_match": "YES",
                "expected_action_problem_match": "NO",
                "expected_platform_match": "UNKNOWN",
                "expected_technology_match": "YES",
                "expected_candidate_should_survive": "YES",
            },
        }

        for case_id, dimensions in expected.items():
            self.assertIn(case_id, cases)
            for field, value in dimensions.items():
                self.assertEqual(cases[case_id][field], value)

    def test_current_main_baseline_is_reproducible(self):
        cases = load_corpus()
        digest = validate_recorded_corpus_sha()

        first = report_as_json(evaluate_current_main(cases, corpus_digest=digest))
        second = report_as_json(evaluate_current_main(cases, corpus_digest=digest))

        self.assertEqual(first, second)
        metrics = first["metrics"]
        self.assertEqual(metrics["BASELINE_CODE_SHA"], "4b53cbc710739a55ff88d0476ad14aafe78e4944")
        self.assertEqual(metrics["MATCHING_BEHAVIOR_BASE_SHA"], "4b53cbc710739a55ff88d0476ad14aafe78e4944")
        self.assertEqual(metrics["TOTAL_CASES"], 200)
        self.assertGreater(metrics["NO_STRUCTURED_TARGET_OVERLAP_COUNT"], 0)
        self.assertEqual(metrics["DELIVERY_POSITIVE_BUCKET"], "STRONG_MATCH")
        self.assertIn("FINAL_MATCH_PRECISION", metrics)
        self.assertIn("FINAL_MATCH_RECALL", metrics)

    def test_current_main_report_matches_committed_baseline_metrics(self):
        cases = load_corpus()
        digest = validate_recorded_corpus_sha()
        report = report_as_json(evaluate_current_main(cases, corpus_digest=digest))

        self.assertEqual(report["metrics"], _baseline_metrics(DEFAULT_BASELINE_PATH))

    def test_final_metric_arithmetic_uses_strong_match_as_positive_class(self):
        cases = load_corpus()
        report = report_as_json(
            evaluate_current_main(cases, corpus_digest=validate_recorded_corpus_sha())
        )
        metrics = report["metrics"]
        tp = metrics["FINAL_TRUE_POSITIVE_COUNT"]
        fp = metrics["FINAL_FALSE_POSITIVE_COUNT"]
        fn = metrics["FINAL_FALSE_NEGATIVE_COUNT"]

        self.assertEqual(
            metrics["FINAL_MATCH_PRECISION"],
            _ratio(tp, tp + fp),
        )
        self.assertEqual(
            metrics["FINAL_MATCH_RECALL"],
            _ratio(tp, tp + fn),
        )

    def test_machine_readable_output_contains_per_case_failure_stage(self):
        cases = load_corpus()
        report = report_as_json(
            evaluate_current_main(cases, corpus_digest=validate_recorded_corpus_sha())
        )

        self.assertEqual(report["schema_version"], "matching-evaluation-report.v1")
        self.assertEqual(len(report["cases"]), 200)
        self.assertTrue(
            all("final_stage" in result for result in report["cases"])
        )
        self.assertTrue(
            all("expected_evidence" in result for result in report["cases"])
        )
        self.assertTrue(
            all(
                result["evidence_contract_status"]
                == "EXPECTED_ONLY_ACTUAL_NOT_EXPOSED_BY_CURRENT_MAIN"
                for result in report["cases"]
            )
        )
        self.assertTrue(
            all(
                result["actual_evidence_or_observable_proxy"]["capability"]
                == "NOT_EXPOSED_BY_CURRENT_MAIN"
                for result in report["cases"]
            )
        )
        self.assertTrue(
            any(
                result["final_stage"] == "narrowing.no_structured_target_overlap"
                for result in report["cases"]
            )
        )


def _baseline_metrics(path: Path) -> dict:
    metrics = {}
    in_metrics = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == "## Metrics":
            in_metrics = True
            continue
        if in_metrics and line.startswith("## "):
            break
        if in_metrics and "=" in line:
            key, value = line.split("=", 1)
            metrics[key] = _parse_metric_value(value)
    return metrics


def _parse_metric_value(value: str):
    if value.isdigit():
        return int(value)
    return value


def _ratio(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0.0000"
    return (Decimal(numerator) / Decimal(denominator)).quantize(
        Decimal("0.0001")
    ).to_eng_string()


if __name__ == "__main__":
    unittest.main()
