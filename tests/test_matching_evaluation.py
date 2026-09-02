from __future__ import annotations

import unittest

from freelancer_bot.matching_evaluation import (
    CAPABILITY_FAMILIES,
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
            "c1a92e4494f43c9a11ecc77243229e10c3c1e9550668270f71da4bfe71835fca",
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

    def test_current_main_baseline_is_reproducible(self):
        cases = load_corpus()
        digest = validate_recorded_corpus_sha()

        first = report_as_json(evaluate_current_main(cases, corpus_digest=digest))
        second = report_as_json(evaluate_current_main(cases, corpus_digest=digest))

        self.assertEqual(first, second)
        metrics = first["metrics"]
        self.assertEqual(metrics["BASELINE_CODE_SHA"], "4b53cbc710739a55ff88d0476ad14aafe78e4944")
        self.assertEqual(metrics["TOTAL_CASES"], 200)
        self.assertGreater(metrics["NO_STRUCTURED_TARGET_OVERLAP_COUNT"], 0)
        self.assertIn("DELIVERY_OR_FINAL_MATCH_PRECISION", metrics)
        self.assertIn("DELIVERY_OR_FINAL_MATCH_RECALL", metrics)

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
            any(
                result["final_stage"] == "narrowing.no_structured_target_overlap"
                for result in report["cases"]
            )
        )


if __name__ == "__main__":
    unittest.main()
