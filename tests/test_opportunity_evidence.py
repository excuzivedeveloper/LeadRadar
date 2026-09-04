from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import unittest
from uuid import UUID

from pydantic import ValidationError

from freelancer_bot.opportunity_analysis import (
    OPPORTUNITY_ANALYSIS_SCHEMA_VERSION,
    OpportunityAnalysis,
)
from freelancer_bot.opportunity_evidence import (
    EvidenceConfidence,
    EvidenceDimension,
    EvidenceItem,
    EvidenceOrigin,
    EvidencePolarity,
    EvidenceShadowDecision,
    EvidenceSource,
    EvidenceVerification,
    OPPORTUNITY_ANALYSIS_V2_SCHEMA_VERSION,
    build_opportunity_analysis_v2,
    derive_profile_evidence,
    evidence_aware_shadow_trace,
    explicit_evidence_is_grounded,
)
from freelancer_bot.persistence.opportunities import (
    CANONICAL_OPPORTUNITY_SCHEMA_VERSION,
    CanonicalOpportunityRecord,
    OpportunityLifecycleStatus,
)
from freelancer_bot.persistence.search_profiles import (
    SearchProfileConfirmationStatus,
    SearchProfileRecord,
)
from freelancer_bot.search_profiles import (
    OpportunityType,
    WorkMode,
    parse_search_profile,
    parse_search_profile_preferences,
)


NOW = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)
FIXTURE_PATH = Path("tests/fixtures/opportunity_evidence_shadow_v2_cases.v1.json")


class OpportunityEvidenceContractTest(unittest.TestCase):
    def test_v2_schema_has_semantic_shadow_fields_and_preserves_v1(self):
        analysis = _analysis()
        v2 = build_opportunity_analysis_v2(
            analysis,
            raw_message_text="Нужен Telegram bot на Python",
        )
        schema = v2.model_json_schema()

        self.assertEqual(v2.schema_version, OPPORTUNITY_ANALYSIS_V2_SCHEMA_VERSION)
        self.assertEqual(v2.base_schema_version, OPPORTUNITY_ANALYSIS_SCHEMA_VERSION)
        self.assertIs(v2.analysis.__class__, OpportunityAnalysis)
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("business_problems", schema["properties"])
        self.assertIn("desired_outcomes", schema["properties"])
        self.assertIn("solution_types", schema["properties"])
        self.assertIn("required_capabilities", schema["properties"])
        self.assertIn("uncertainties", schema["properties"])
        self.assertEqual(analysis.schema_version, OPPORTUNITY_ANALYSIS_SCHEMA_VERSION)

    def test_evidence_item_axes_are_independent_and_validated(self):
        base = {
            "dimension": "platform",
            "concept_id": "vk",
            "label": "VK",
            "origin": "raw_explicit",
            "source": "opportunity",
            "raw_span": "вк",
            "field_path": "raw_message_text",
            "verification": "raw_span_verified",
            "confidence": "high",
            "polarity": "positive",
            "authoritative": True,
            "verifier_version": "explicit-evidence-verifier.v2",
        }
        parsed = EvidenceItem.model_validate_json(json.dumps(base), strict=True)

        self.assertEqual(parsed.verification, EvidenceVerification.RAW_SPAN_VERIFIED)
        self.assertEqual(parsed.confidence, EvidenceConfidence.HIGH)
        self.assertEqual(parsed.polarity, EvidencePolarity.POSITIVE)
        self.assertTrue(parsed.counts_as_positive)

        invalid_cases = (
            {**base, "verification": "model_only"},
            {**base, "polarity": "negated"},
            {**base, "confidence": "low"},
        )
        for payload in invalid_cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    EvidenceItem.model_validate_json(json.dumps(payload), strict=True)

    def test_raw_message_fastapi_hallucination_control(self):
        v2 = build_opportunity_analysis_v2(
            _analysis(skills=("FastAPI",), task_summary="Нужен ИИ-менеджер для заявок"),
            raw_message_text="Нужен ИИ-менеджер для заявок",
        )

        fastapi = _items(v2.evidence).get(("technology", "fastapi"))

        self.assertIsNone(fastapi)

    def test_raw_message_fastapi_true_explicit_control(self):
        v2 = build_opportunity_analysis_v2(
            _analysis(skills=("FastAPI",), task_summary="Нужен FastAPI разработчик"),
            raw_message_text="Нужен FastAPI разработчик",
        )
        fastapi = _items(v2.evidence)[("technology", "fastapi")]

        self.assertEqual(fastapi.origin, EvidenceOrigin.RAW_EXPLICIT)
        self.assertEqual(fastapi.verification, EvidenceVerification.RAW_SPAN_VERIFIED)
        self.assertTrue(explicit_evidence_is_grounded(fastapi, "Нужен FastAPI разработчик"))

    def test_negated_react_and_not_telegram_use_vk_controls(self):
        for raw_text in ("React не нужен", "без React"):
            with self.subTest(raw_text=raw_text):
                v2 = build_opportunity_analysis_v2(
                    _analysis(skills=("React",), task_summary=raw_text),
                    raw_message_text=raw_text,
                )
                trace = evidence_aware_shadow_trace(
                    v2,
                    _profile(
                        roles=("React developer",),
                        skills=("React",),
                        categories=("frontend",),
                        semantic_text="React",
                    ),
                )
                react = _items(v2.evidence)[("technology", "react")]

                self.assertEqual(react.polarity, EvidencePolarity.NEGATED)
                self.assertFalse(react.counts_as_positive)
                self.assertFalse(any(match.counts_as_positive for match in trace.matches))
                self.assertEqual(trace.decision, EvidenceShadowDecision.NO_EVIDENCE_MATCH)

        v2 = build_opportunity_analysis_v2(
            _analysis(
                category="VK automation",
                role_title="VK bot",
                skills=("Telegram",),
                task_summary="не Telegram, нужен VK",
            ),
            raw_message_text="не Telegram, нужен VK",
        )
        evidence = _items(v2.evidence)

        self.assertEqual(evidence[("platform", "telegram")].polarity, EvidencePolarity.NEGATED)
        self.assertEqual(evidence[("platform", "vk")].polarity, EvidencePolarity.POSITIVE)

    def test_internal_llm_api_is_not_openai_raw_explicit(self):
        v2 = build_opportunity_analysis_v2(
            _analysis(
                category="AI integration",
                role_title="LLM integration",
                skills=("internal LLM API",),
                task_summary="Need integration with our internal LLM API",
            ),
            raw_message_text="Need integration with our internal LLM API",
        )
        evidence = _items(v2.evidence)

        self.assertNotIn(("technology", "openai_api"), evidence)
        self.assertIn(("capability", "llm_ai_integration"), evidence)

    def test_generic_guard_blocks_generic_only_combinations(self):
        cases = (
            (
                "Need bot website",
                _analysis(category="bot website", role_title="bot website", task_summary="bot website"),
                _profile(roles=("Bot website developer",), skills=(), categories=("web",), semantic_text="bot web"),
            ),
            (
                "AI automation",
                _analysis(category="AI automation", role_title="AI automation", task_summary="AI automation"),
                _profile(roles=("Automation specialist",), skills=(), categories=("automation",), semantic_text="automation"),
            ),
            (
                "backend web",
                _analysis(category="backend web", role_title="backend web", task_summary="backend web"),
                _profile(roles=("Backend web developer",), skills=(), categories=("web",), semantic_text="backend web"),
            ),
        )

        for raw_text, analysis, profile in cases:
            with self.subTest(raw_text=raw_text):
                trace = evidence_aware_shadow_trace(
                    build_opportunity_analysis_v2(analysis, raw_message_text=raw_text),
                    profile,
                )

                self.assertTrue(trace.generic_signal_blocked)
                self.assertEqual(trace.decision, EvidenceShadowDecision.WEAK_OR_GENERIC)
                self.assertLess(trace.score, Decimal("0.4000"))

    def test_profile_semantic_text_cannot_mint_authoritative_capability(self):
        semantic_only = _profile(
            roles=("Designer",),
            skills=("Figma",),
            categories=("UI",),
            semantic_text="React Next.js web apps",
        )
        structured = _profile(
            roles=("Designer",),
            skills=("React", "Next.js"),
            categories=("UI",),
            semantic_text="general web summary",
        )

        semantic_items = _items(derive_profile_evidence(semantic_only).evidence)
        structured_items = _items(derive_profile_evidence(structured).evidence)

        self.assertFalse(
            semantic_items[("capability", "react_next_web")].authoritative
        )
        self.assertEqual(
            semantic_items[("capability", "react_next_web")].origin,
            EvidenceOrigin.SEMANTIC_TEXT_HINT,
        )
        self.assertTrue(structured_items[("capability", "react_next_web")].authoritative)
        self.assertEqual(
            structured_items[("capability", "react_next_web")].origin,
            EvidenceOrigin.DERIVED_RULE,
        )

    def test_shadow_trace_dedupes_synonyms_by_dimension_and_concept(self):
        v2 = build_opportunity_analysis_v2(
            _analysis(
                category="web dashboard",
                role_title="React Next.js developer",
                skills=("React", "Next.js"),
                task_summary="Build React ReactJS and Next.js next js dashboard.",
            ),
            raw_message_text="Build React ReactJS and Next.js next js dashboard.",
        )
        trace = evidence_aware_shadow_trace(
            v2,
            _profile(
                roles=("Frontend engineer",),
                skills=("React", "Next.js"),
                categories=("web development",),
                semantic_text="React Next.js web apps",
            ),
        )

        identities = [(match.dimension, match.concept_id) for match in trace.matches]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertIn((EvidenceDimension.CAPABILITY, "react_next_web"), identities)
        self.assertTrue(trace.current_policy_changed is False)
        self.assertTrue(trace.shadow_weights_experimental)
        self.assertTrue(trace.shadow_score_not_production_policy)

    def test_versioned_fixture_drives_behavioral_assertions(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            fixture["schema_version"],
            "opportunity-evidence-shadow-v2-cases.v2",
        )
        families = {
            family: sum(case["family"] == family for case in fixture["cases"])
            for family in ("conversational", "technical", "boundary")
        }
        self.assertGreaterEqual(families["conversational"], 10)
        self.assertGreaterEqual(families["technical"], 4)
        self.assertGreaterEqual(families["boundary"], 14)

        for case in fixture["cases"]:
            with self.subTest(case_id=case["case_id"]):
                v2 = build_opportunity_analysis_v2(
                    _analysis(**case["opportunity"]),
                    raw_message_text=case["raw_message_text"],
                )
                trace = evidence_aware_shadow_trace(v2, _profile(**case["profile"]))
                evidence = _items(v2.evidence)
                positive = {
                    key
                    for key, item in evidence.items()
                    if item.counts_as_positive
                }
                non_positive = {
                    key
                    for key, item in evidence.items()
                    if not item.counts_as_positive
                }

                for dimension, concept in case["expected_positive"]:
                    self.assertIn((dimension, concept), positive)
                for dimension, concept in case["expected_absent"]:
                    self.assertNotIn((dimension, concept), evidence)
                for dimension, concept in case["expected_non_positive"]:
                    self.assertIn((dimension, concept), non_positive)
                self.assertEqual(trace.decision.value, case["expected_decision"])

    def test_current_match_decision_regression_stays_outside_shadow(self):
        opportunity = _opportunity_record(_analysis())
        v2 = build_opportunity_analysis_v2(
            opportunity.analysis,
            raw_message_text="Нужен Telegram bot на Python",
        )
        shadow = evidence_aware_shadow_trace(v2, _profile())

        self.assertEqual(opportunity.analysis.schema_version, "opportunity_analysis.v1")
        self.assertFalse(shadow.current_policy_changed)


def _items(evidence: tuple[EvidenceItem, ...]) -> dict[tuple[str, str], EvidenceItem]:
    return {(item.dimension.value, item.concept_id): item for item in evidence}


def _analysis(
    *,
    category: str = "telegram_development",
    role_title: str = "Telegram bot developer",
    skills: tuple[str, ...] | list[str] = ("Python", "Telegram Bot API"),
    task_summary: str = "Build a Telegram bot",
) -> OpportunityAnalysis:
    return OpportunityAnalysis.model_validate_json(
        json.dumps(
            {
                "schema_version": OPPORTUNITY_ANALYSIS_SCHEMA_VERSION,
                "is_opportunity": True,
                "confidence": 0.94,
                "market_direction": "buyer_to_specialist",
                "intent_stage": "active",
                "opportunity_type": "project",
                "category": category,
                "role_title": role_title,
                "skills": list(skills),
                "task_summary": task_summary,
                "budget": {
                    "known": False,
                    "min": None,
                    "max": None,
                    "currency": None,
                    "period": None,
                    "explicit": False,
                },
                "work": {
                    "remote": True,
                    "location": None,
                    "full_time": None,
                    "part_time": None,
                },
                "language": "ru",
                "contact": {"telegram": None, "email": None, "url": None},
                "quality": {
                    "actionability": 0.9,
                    "commercial_plausibility": 0.8,
                    "specificity": 0.7,
                    "credibility": 0.8,
                },
                "red_flags": [],
            },
            ensure_ascii=False,
        ),
        strict=True,
    )


def _opportunity_record(analysis: OpportunityAnalysis) -> CanonicalOpportunityRecord:
    return CanonicalOpportunityRecord(
        id=UUID("10000000-0000-0000-0000-000000000001"),
        schema_version=CANONICAL_OPPORTUNITY_SCHEMA_VERSION,
        canonical_title=analysis.role_title,
        task_summary=analysis.task_summary,
        analysis=analysis,
        first_seen_at=NOW,
        last_seen_at=NOW,
        lifecycle_status=OpportunityLifecycleStatus.ACTIVE,
        lifecycle_changed_at=NOW,
        raw_message_ids=(),
        analysis_cache_ids=(),
        analysis_links=(),
        preferred_source_policy_version=None,
        preferred_source=None,
        source_observations=(),
        lifecycle_events=(),
        created_at=NOW,
        updated_at=NOW,
    )


def _profile(
    *,
    roles=("Python Telegram bot developer",),
    skills=("Python", "aiogram"),
    categories=("Telegram",),
    semantic_text="Python aiogram Telegram bot development",
) -> SearchProfileRecord:
    parsed = parse_search_profile(
        roles=roles,
        skills=skills,
        categories=categories,
        semantic_text=semantic_text,
    )
    preferences = parse_search_profile_preferences(
        work_types=(OpportunityType.PROJECT,),
        minimum_budget="100000",
        currency="RUB",
        work_modes=(WorkMode.REMOTE,),
    )
    return SearchProfileRecord(
        id=UUID("20000000-0000-0000-0000-000000000001"),
        user_id=UUID("30000000-0000-0000-0000-000000000001"),
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
        confirmed_at=NOW,
        is_active=True,
        is_primary=True,
        activated_at=NOW,
        deactivated_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


if __name__ == "__main__":
    unittest.main()
