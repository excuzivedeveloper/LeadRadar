from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import unittest

from freelancer_bot.match_decisions import (
    MatchDecisionCode,
    MatchDecisionPolicy,
    MatchScoringInput,
    decide_and_rank_matches,
)
from freelancer_bot.matching import CandidateExclusionCode, narrow_and_filter_candidates
from freelancer_bot.matching_evidence import EvidenceMatch, derive_matching_evidence
from freelancer_bot.search_profiles import OpportunityType
from freelancer_bot.semantic_matching import (
    DeterministicHashEmbeddingProvider,
    score_candidates_semantic,
)
from tests.test_semantic_matching import NOW, _opportunity as _base_opportunity
from tests.test_semantic_matching import _profile as _base_profile


class MatchingSuccessorTest(unittest.TestCase):
    def test_owner_mvp_canary_regression_fixture_is_sanitized_and_bounded(self):
        fixture = json.loads(
            Path("tests/fixtures/owner_mvp_canary_matching_regressions.v1.json")
            .read_text(encoding="utf-8")
        )

        self.assertEqual(
            fixture["schema_version"],
            "owner-mvp-canary-matching-regressions.v1",
        )
        self.assertEqual(
            {case["case_id"] for case in fixture["cases"]},
            {
                "owner_mvp_ru_en_web_positive_a",
                "owner_mvp_ru_en_web_positive_b",
                "owner_mvp_opencart_seo_control",
            },
        )

    def test_owner_mvp_canary_ru_profile_survives_en_react_next_web_case(self):
        trace = _decision_trace(
            _opportunity(
                role_title="Full-stack React Next.js developer",
                skills=("React", "Next.js", "JavaScript", "TypeScript"),
                category="web development",
                task_summary="Build a React/Next web application and integrate product features.",
                language=None,
                location=None,
            ),
            _owner_web_profile(),
        )

        self.assertTrue(trace.hard_filter_eligible)
        self.assertTrue(trace.eligible)
        self.assertNotEqual(trace.decision_code, MatchDecisionCode.BELOW_RELEVANCE_THRESHOLD)

    def test_owner_mvp_canary_ru_profile_survives_en_product_integration_case(self):
        trace = _decision_trace(
            _opportunity(
                role_title="Full-stack product engineer",
                skills=("React", "Next.js", "API integration"),
                category="website development",
                task_summary="Need full stack product integration for a Next.js customer portal.",
                language=None,
                location=None,
            ),
            _owner_web_profile(),
        )

        self.assertTrue(trace.hard_filter_eligible)
        self.assertTrue(trace.eligible)
        self.assertNotEqual(trace.decision_code, MatchDecisionCode.BELOW_RELEVANCE_THRESHOLD)

    def test_owner_mvp_canary_opencart_seo_control_is_not_forced_eligible(self):
        trace = _decision_trace(
            _opportunity(
                role_title="OpenCart SEO specialist",
                skills=("OpenCart", "SEO"),
                category="website",
                task_summary="Need OpenCart SEO fixes and catalog metadata cleanup.",
                language=None,
                location=None,
            ),
            _owner_web_profile(),
        )

        self.assertTrue(trace.hard_filter_eligible)
        self.assertFalse(trace.eligible)
        self.assertEqual(trace.decision_code, MatchDecisionCode.BELOW_RELEVANCE_THRESHOLD)

    def test_weak_relevant_without_exact_target_overlap_survives_retrieval(self):
        opportunity = _opportunity(
            role_title="Webhook integration builder",
            skills=("FastAPI",),
            category="CRM automation",
            task_summary="Need Python API webhook sync for orders.",
        )
        profile = _profile(
            roles=("Backend engineer",),
            skills=("Python",),
            categories=("API integrations",),
            semantic_text="Python backend integrations and webhook services",
        )

        result = narrow_and_filter_candidates(opportunity, (profile,))

        self.assertEqual(result.eligible_profiles, (profile,))
        self.assertEqual(
            tuple(exclusion.code for exclusion in result.trace.exclusions),
            (CandidateExclusionCode.NO_STRUCTURED_TARGET_OVERLAP,),
        )

    def test_website_chatbot_is_not_final_telegram_match(self):
        trace = _decision_trace(
            _opportunity(
                role_title="Website chatbot developer",
                skills=("JavaScript",),
                category="website chatbot",
                task_summary="Build a support chatbot widget for a website.",
            ),
            _profile(
                roles=("Telegram bot developer",),
                skills=("Python", "aiogram"),
                categories=("Telegram",),
                semantic_text="Build Telegram bots with Python and aiogram",
            ),
        )

        self.assertFalse(trace.eligible)
        self.assertEqual(trace.decision_code, MatchDecisionCode.BELOW_RELEVANCE_THRESHOLD)

    def test_generic_backend_does_not_invent_fastapi_technology_evidence(self):
        opportunity = _opportunity(
            role_title="FastAPI backend developer",
            skills=("FastAPI", "Python"),
            category="backend",
            task_summary="Build FastAPI endpoints and webhooks.",
        )
        profile = _profile(
            roles=("Backend developer",),
            skills=("REST API",),
            categories=("backend",),
            semantic_text="Generic backend services and integrations",
        )

        evidence = derive_matching_evidence(opportunity.analysis, profile)

        self.assertIs(evidence.technology.value, EvidenceMatch.UNKNOWN)
        self.assertNotIn("fastapi", evidence.technology.evidence)

    def test_bot_moderation_is_not_bot_development_delivery(self):
        trace = _decision_trace(
            _opportunity(
                role_title="Telegram bot developer",
                skills=("Python", "aiogram"),
                category="Telegram",
                task_summary="Build a Telegram bot for lead routing.",
            ),
            _profile(
                roles=("Telegram community moderator",),
                skills=("moderation",),
                categories=("Telegram",),
                semantic_text="Moderate Telegram chats and support communities",
            ),
        )

        self.assertFalse(trace.eligible)
        self.assertEqual(trace.decision_code, MatchDecisionCode.BELOW_RELEVANCE_THRESHOLD)

    def test_telegram_python_aiogram_is_strong_final_match(self):
        trace = _decision_trace(
            _opportunity(
                role_title="Telegram bot developer",
                skills=("Python", "aiogram"),
                category="Telegram",
                task_summary="Build Telegram bot automation with aiogram.",
            ),
            _profile(
                roles=("Python Telegram bot developer",),
                skills=("Python", "aiogram"),
                categories=("Telegram",),
                semantic_text="Python aiogram Telegram bot development",
            ),
        )

        self.assertTrue(trace.eligible)
        self.assertEqual(trace.decision_code, MatchDecisionCode.ELIGIBLE)

    def test_fastapi_api_webhook_project_scores_backend_profile(self):
        trace = _decision_trace(
            _opportunity(
                role_title="Python backend developer",
                skills=("FastAPI", "Python"),
                category="backend",
                task_summary="Build FastAPI API endpoints and webhook processing.",
            ),
            _profile(
                roles=("Python backend engineer",),
                skills=("Python", "FastAPI"),
                categories=("backend",),
                semantic_text="Python FastAPI backend API and webhook services",
            ),
        )

        self.assertTrue(trace.hard_filter_eligible)
        self.assertTrue(trace.eligible)

    def test_playwright_scraping_automation_scores_browser_profile(self):
        trace = _decision_trace(
            _opportunity(
                role_title="Browser automation developer",
                skills=("Playwright", "Python"),
                category="browser automation",
                task_summary="Build Playwright scraping automation for web forms.",
            ),
            _profile(
                roles=("Browser automation engineer",),
                skills=("Playwright", "Python"),
                categories=("browser automation",),
                semantic_text="Playwright browser automation and scraping",
            ),
        )

        self.assertTrue(trace.hard_filter_eligible)
        self.assertTrue(trace.eligible)

    def test_explicit_hard_constraint_rejects_remain_rejects(self):
        trace = _decision_trace(
            _opportunity(language="English"),
            _profile(preferences_languages=("Russian",)),
        )

        self.assertFalse(trace.hard_filter_eligible)
        self.assertEqual(trace.decision_code, MatchDecisionCode.HARD_REJECTED)


def _decision_trace(opportunity, profile):
    semantic = score_candidates_semantic(
        opportunity,
        (profile,),
        provider=DeterministicHashEmbeddingProvider(),
    )
    return decide_and_rank_matches(
        (MatchScoringInput(opportunity, (profile,), semantic),),
        evaluated_at=NOW,
        policy=MatchDecisionPolicy(),
    ).traces[0]


def _opportunity(*, language="English", location="Berlin", **overrides):
    opportunity = _base_opportunity(**overrides)
    analysis = opportunity.analysis.model_copy(
        update={
            "language": language,
            "work": opportunity.analysis.work.model_copy(
                update={"location": location}
            ),
        }
    )
    return replace(opportunity, analysis=analysis)


def _profile(*, preferences_languages=("English",), **overrides):
    from freelancer_bot.search_profiles import (
        BudgetPolicy,
        WorkMode,
        parse_search_profile_preferences,
    )

    preferences = parse_search_profile_preferences(
        work_types=(OpportunityType.PROJECT,),
        minimum_budget="100000",
        currency="RUB",
        budget_policy=BudgetPolicy.ALLOW_UNKNOWN,
        languages=preferences_languages,
        geographies=("Berlin",),
        work_modes=(WorkMode.REMOTE,),
        excluded_categories=(),
    )
    return replace(_base_profile(**overrides), preferences=preferences)


def _owner_web_profile():
    return _profile(
        roles=("Full-stack разработчик",),
        skills=("JavaScript", "TypeScript", "React", "Next.js"),
        categories=("веб-разработка",),
        semantic_text=(
            "веб-разработка | Full-stack разработчик | JavaScript | "
            "TypeScript | React | Next.js"
        ),
        preferences_languages=None,
    )
