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
            "e00537a731387d924916f3a4da895f06950a4788311d055eed708ca740449564",
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

    def test_curated_language_labels_match_main_prose_examples(self):
        cases = {case.case_id: case.raw for case in load_corpus()}

        examples = {
            "ru_telegram_automation_strong_004": "RU",
            "en_telegram_automation_strong_005": "EN",
            "mixed_python_backend_api_strong_002": "MIXED",
            "ru_business_automation_strong_004": "RU",
            "en_monitoring_alerting_strong_003": "EN",
            "mixed_monitoring_alerting_strong_004": "MIXED",
            "ru_hard_worktype_001": "RU",
            "mixed_hard_geography_003": "MIXED",
        }

        for case_id, language in examples.items():
            self.assertEqual(cases[case_id]["language"], language)
            _assert_main_prose_language(self, cases[case_id], language)

    def test_mixed_cases_are_not_english_only_or_plain_russian_tech_names(self):
        for case in load_corpus():
            if case.raw["language"] == "MIXED":
                summary = case.raw["opportunity"]["task_summary"]
                self.assertRegex(summary, r"[А-Яа-яЁё]")
                self.assertRegex(summary, r"[A-Za-z]{3,}")

    def test_non_match_adversarial_variants_are_materially_distinct(self):
        cases = [
            case.raw
            for case in load_corpus()
            if case.raw["expected_bucket"] == "NON_MATCH"
        ]
        summaries = [case["opportunity"]["task_summary"] for case in cases]

        self.assertEqual(len(cases), 60)
        self.assertEqual(len(set(summaries)), 60)
        self.assertFalse(any("Variant " in summary for summary in summaries))
        self.assertFalse(any("Вариант " in summary for summary in summaries))

        repaired = [
            case
            for case in cases
            if 23 <= int(case["case_id"].split("_adversarial_")[1][:3]) <= 60
        ]
        self.assertEqual(len(repaired), 38)
        self.assertEqual(
            len({case["opportunity"]["role_title"] for case in repaired}),
            len(repaired),
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

        self.assertEqual(
            report["frozen_baseline_metrics"],
            _baseline_metrics(DEFAULT_BASELINE_PATH),
        )
        self.assertNotEqual(report["metrics"], report["frozen_baseline_metrics"])
        self.assertIn("delta_metrics", report)

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

    def test_next_2b_successor_acceptance_gates_are_met(self):
        cases = load_corpus()
        report = report_as_json(
            evaluate_current_main(cases, corpus_digest=validate_recorded_corpus_sha())
        )
        metrics = report["metrics"]

        self.assertEqual(metrics["STRONG_MATCH_SURVIVAL_RECALL"], "1.0000")
        self.assertGreaterEqual(
            Decimal(metrics["WEAK_VALID_SURVIVAL_RECALL"]),
            Decimal("0.8000"),
        )
        self.assertGreaterEqual(
            Decimal(metrics["CANDIDATE_SURVIVAL_RECALL"]),
            Decimal("0.9000"),
        )
        self.assertEqual(metrics["HARD_CONSTRAINT_REJECT_ACCURACY"], "1.0000")
        self.assertEqual(metrics["FINAL_MATCH_RECALL"], "1.0000")
        self.assertGreaterEqual(
            Decimal(metrics["FINAL_MATCH_PRECISION"]),
            Decimal("0.7500"),
        )
        self.assertIn("NO_STRUCTURED_TARGET_OVERLAP_DIAGNOSTIC_COUNT", metrics)

    def test_machine_readable_output_contains_per_case_failure_stage(self):
        cases = load_corpus()
        report = report_as_json(
            evaluate_current_main(cases, corpus_digest=validate_recorded_corpus_sha())
        )

        self.assertEqual(report["schema_version"], "matching-evaluation-report.v2")
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
                == "EXPOSED_BY_MATCHING_SUCCESSOR"
                for result in report["cases"]
            )
        )
        self.assertTrue(
            all(
                "match"
                in result["actual_evidence_or_observable_proxy"]["capability"]
                for result in report["cases"]
            )
        )
        self.assertTrue(
            any(
                result["final_stage"] == "final_relevance_reject"
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


def _assert_main_prose_language(
    test_case: unittest.TestCase,
    raw_case: dict,
    language: str,
) -> None:
    summary = raw_case["opportunity"]["task_summary"]
    has_cyrillic = any("А" <= char <= "я" or char in "Ёё" for char in summary)
    has_latin_word = any(
        part.isascii() and any(char.isalpha() for char in part)
        for part in summary.replace("/", " ").replace("-", " ").split()
    )
    if language == "RU":
        test_case.assertTrue(has_cyrillic)
    elif language == "EN":
        test_case.assertFalse(has_cyrillic)
    elif language == "MIXED":
        test_case.assertTrue(has_cyrillic)
        test_case.assertTrue(has_latin_word)
    else:
        test_case.fail(f"unknown language label: {language}")


if __name__ == "__main__":
    unittest.main()
