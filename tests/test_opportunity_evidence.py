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
    EvidenceDimension,
    EvidenceItem,
    EvidenceOrigin,
    EvidenceShadowDecision,
    EvidenceSource,
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
    def test_opportunity_analysis_v2_schema_and_v1_backward_compatibility(self):
        analysis = _analysis()
        v2 = build_opportunity_analysis_v2(analysis)
        schema = v2.model_json_schema()

        self.assertEqual(v2.schema_version, OPPORTUNITY_ANALYSIS_V2_SCHEMA_VERSION)
        self.assertEqual(v2.base_schema_version, OPPORTUNITY_ANALYSIS_SCHEMA_VERSION)
        self.assertIs(v2.analysis.__class__, OpportunityAnalysis)
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(analysis.schema_version, OPPORTUNITY_ANALYSIS_SCHEMA_VERSION)

    def test_evidence_item_validation_blocks_unverified_explicit_evidence(self):
        payload = {
            "dimension": "platform",
            "concept_id": "vk",
            "label": "VK",
            "origin": "explicit",
            "source": "opportunity",
            "raw_span": "вк",
            "field_path": "analysis.task_summary",
            "verified": False,
            "verifier_version": "explicit-evidence-verifier.v1",
        }

        with self.assertRaises(ValidationError):
            EvidenceItem.model_validate(payload, strict=True)

    def test_raw_span_verifier_accepts_only_exact_supplied_text(self):
        item = EvidenceItem(
            dimension=EvidenceDimension.PLATFORM,
            concept_id="vk",
            label="VK",
            origin=EvidenceOrigin.EXPLICIT,
            source=EvidenceSource.OPPORTUNITY,
            raw_span="вк",
            field_path="analysis.task_summary",
            verified=True,
            verifier_version="explicit-evidence-verifier.v1",
        )

        self.assertTrue(
            explicit_evidence_is_grounded(
                item,
                {"analysis.task_summary": "Нужен ИИ-менеджер в ВК"},
            )
        )
        self.assertFalse(
            explicit_evidence_is_grounded(
                item,
                {"analysis.task_summary": "Нужен ИИ-менеджер"},
            )
        )

    def test_vk_ai_manager_preserves_explicit_vs_inferred_boundary(self):
        analysis = _analysis(
            category="ai assistant",
            role_title="ИИ-менеджер в ВК",
            skills=(),
            task_summary="Нужен ИИ-менеджер в ВК для обработки заявок.",
        )

        v2 = build_opportunity_analysis_v2(analysis)
        evidence = {
            (item.dimension.value, item.concept_id): item for item in v2.evidence
        }

        self.assertEqual(evidence[("platform", "vk")].origin, EvidenceOrigin.EXPLICIT)
        self.assertTrue(evidence[("platform", "vk")].verified)
        self.assertEqual(
            evidence[("solution_type", "ai_assistant")].origin,
            EvidenceOrigin.EXPLICIT,
        )
        self.assertEqual(
            evidence[("capability", "chat_automation")].origin,
            EvidenceOrigin.INFERRED,
        )
        self.assertEqual(
            evidence[("capability", "lead_handling")].origin,
            EvidenceOrigin.INFERRED,
        )
        self.assertNotIn(("technology", "openai_api"), evidence)
        self.assertNotIn(("technology", "fastapi"), evidence)
        self.assertNotIn(("technology", "react"), evidence)
        self.assertNotIn(("technology", "python"), evidence)

    def test_search_profile_capabilities_are_derived_deterministically(self):
        profile = _profile(
            roles=("Backend engineer",),
            skills=("FastAPI", "Playwright", "OpenAI-compatible API"),
            categories=("Telegram automation",),
            semantic_text=(
                "React Next.js web apps, OpenAI-compatible APIs, FastAPI "
                "webhooks, Playwright browser automation, Telegram aiogram bots"
            ),
        )

        concepts = {
            (item.dimension.value, item.concept_id): item
            for item in derive_profile_evidence(profile).evidence
        }

        for concept in (
            "react_next_web",
            "llm_ai_integration",
            "backend_api",
            "api_webhook_integration",
            "browser_automation",
            "telegram_automation",
        ):
            self.assertIn(("capability", concept), concepts)
            self.assertIn(
                concepts[("capability", concept)].origin,
                {EvidenceOrigin.DERIVED, EvidenceOrigin.INFERRED},
            )

    def test_shadow_trace_dedupes_by_dimension_and_concept(self):
        trace = evidence_aware_shadow_trace(
            _analysis(
                category="web dashboard",
                role_title="React Next.js developer",
                skills=("React", "Next.js"),
                task_summary="Build React and Next.js dashboard in React.",
            ),
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

    def test_generic_signal_guard_blocks_bot_only_match(self):
        trace = evidence_aware_shadow_trace(
            _analysis(
                category="bot",
                role_title="AI bot",
                skills=(),
                task_summary="Need an AI bot.",
            ),
            _profile(
                roles=("Bot developer",),
                skills=(),
                categories=("automation",),
                semantic_text="bot automation",
            ),
        )

        self.assertTrue(trace.generic_signal_blocked)
        self.assertEqual(trace.decision, EvidenceShadowDecision.WEAK_OR_GENERIC)
        self.assertLess(trace.score, Decimal("0.4000"))

    def test_versioned_conversational_boundary_fixture(self):
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            fixture["schema_version"],
            "opportunity-evidence-shadow-v2-cases.v1",
        )
        self.assertEqual(len({case["case_id"] for case in fixture["cases"]}), 3)
        for case in fixture["cases"]:
            with self.subTest(case_id=case["case_id"]):
                analysis = _analysis(**case["opportunity"])
                profile = _profile(**case["profile"])
                v2 = build_opportunity_analysis_v2(analysis)
                trace = evidence_aware_shadow_trace(v2, profile)
                expected = case["expected"]
                opportunity_concepts = {
                    (item.dimension.value, item.concept_id) for item in v2.evidence
                }

                if expected.get("platform"):
                    self.assertIn(
                        ("platform", expected["platform"]),
                        opportunity_concepts,
                    )
                if expected.get("solution_type"):
                    self.assertIn(
                        ("solution_type", expected["solution_type"]),
                        opportunity_concepts,
                    )
                for concept in expected.get("must_not_infer_technologies", []):
                    self.assertNotIn(("technology", concept), opportunity_concepts)
                if "generic_signal_blocked" in expected:
                    self.assertEqual(
                        trace.generic_signal_blocked,
                        expected["generic_signal_blocked"],
                    )
                if "deduped_match_count_max" in expected:
                    self.assertLessEqual(
                        trace.deduped_match_count,
                        expected["deduped_match_count_max"],
                    )
                self.assertEqual(trace.decision.value, expected["shadow_decision"])

    def test_current_match_decision_regression_stays_outside_shadow(self):
        opportunity = _opportunity_record(
            _analysis(
                category="bot",
                role_title="AI bot",
                skills=(),
                task_summary="Need an AI bot.",
            )
        )
        shadow = evidence_aware_shadow_trace(opportunity.analysis, _profile())

        self.assertEqual(opportunity.analysis.schema_version, "opportunity_analysis.v1")
        self.assertFalse(shadow.current_policy_changed)


def _analysis(
    *,
    category: str = "telegram_development",
    role_title: str = "Telegram bot developer",
    skills: tuple[str, ...] = ("Python", "Telegram Bot API"),
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
