from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import json
import unittest
from uuid import uuid4

import sqlalchemy as sa

from freelancer_bot.matching import (
    CandidateExclusionCode,
    HardFilterCode,
    UnknownMatchField,
    evaluate_hard_filters,
    narrow_and_filter_candidates,
)
from freelancer_bot.matching_service import CandidateMatchingService
from freelancer_bot.opportunity_analysis import OpportunityAnalysis
from freelancer_bot.persistence.database import Database
from freelancer_bot.persistence.opportunities import (
    CANONICAL_OPPORTUNITY_SCHEMA_VERSION,
    CanonicalOpportunityRecord,
    OpportunityLifecycleStatus,
    OpportunitySourceObservationRecord,
)
from freelancer_bot.persistence.schema import (
    collector_accounts,
    durable_jobs,
    opportunities,
    opportunity_source_messages,
    raw_messages,
    sources,
)
from freelancer_bot.opportunity_dedup import PREFERRED_SOURCE_POLICY_VERSION
from freelancer_bot.persistence.search_profiles import (
    SearchProfileConfirmationStatus,
    SearchProfileRecord,
)
from freelancer_bot.profile_confirmation import ProfileConfirmationService
from freelancer_bot.search_profiles import (
    BudgetPolicy,
    OpportunityType,
    WorkMode,
    parse_search_profile,
    parse_search_profile_preferences,
)
from postgres_support import TEST_DATABASE_URL, migrate_to_head, temporary_database


NOW = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)


class MatchingHardFilterTest(unittest.TestCase):
    def test_unknown_negotiable_and_known_budgets_follow_explicit_policy(self):
        allow_unknown = _profile(
            preferences=_preferences(
                minimum_budget="100000",
                currency="RUB",
                budget_policy=BudgetPolicy.ALLOW_UNKNOWN,
            )
        )
        require_explicit = replace(
            allow_unknown,
            id=uuid4(),
            preferences=_preferences(
                minimum_budget="100000",
                currency="RUB",
                budget_policy=BudgetPolicy.REQUIRE_EXPLICIT,
            ),
        )

        unknown = _opportunity(budget=_budget(known=False, explicit=False))
        negotiable = _opportunity(
            budget=_budget(known=False, explicit=True),
        )
        under_minimum = _opportunity(
            budget=_budget(
                known=True,
                explicit=True,
                minimum=50000,
                maximum=90000,
                currency="RUB",
            )
        )
        sufficient = _opportunity(
            budget=_budget(
                known=True,
                explicit=True,
                minimum=100000,
                maximum=120000,
                currency="RUB",
            )
        )

        self.assertTrue(evaluate_hard_filters(unknown, allow_unknown).eligible)
        required_unknown = evaluate_hard_filters(unknown, require_explicit)
        self.assertEqual(
            _failure_codes(required_unknown),
            {HardFilterCode.BUDGET_NOT_EXPLICIT},
        )
        self.assertTrue(evaluate_hard_filters(negotiable, require_explicit).eligible)
        self.assertEqual(
            _failure_codes(evaluate_hard_filters(under_minimum, allow_unknown)),
            {HardFilterCode.BUDGET_BELOW_MINIMUM},
        )
        self.assertTrue(evaluate_hard_filters(sufficient, allow_unknown).eligible)

        different_currency = replace(
            sufficient,
            analysis=_analysis(
                budget=_budget(
                    known=True,
                    explicit=True,
                    minimum=500,
                    maximum=700,
                    currency="USD",
                )
            ),
        )
        decision = evaluate_hard_filters(different_currency, allow_unknown)
        self.assertTrue(decision.eligible)
        self.assertIn(
            UnknownMatchField.BUDGET_CURRENCY,
            decision.nonblocking_unknowns,
        )

    def test_independent_explicit_constraints_produce_explainable_failures(self):
        profile = _profile(
            preferences=_preferences(
                work_types=(OpportunityType.VACANCY,),
                languages=("Русский",),
                geographies=("Москва",),
                work_modes=(WorkMode.ON_SITE,),
                excluded_categories=("Gambling",),
            )
        )
        opportunity = _opportunity(
            analysis=_analysis(
                opportunity_type="project",
                category="Gambling",
                language="English",
                location="Berlin",
                remote=True,
            )
        )

        decision = evaluate_hard_filters(opportunity, profile)

        self.assertFalse(decision.eligible)
        self.assertEqual(
            _failure_codes(decision),
            {
                HardFilterCode.WORK_TYPE_MISMATCH,
                HardFilterCode.EXCLUDED_CATEGORY,
                HardFilterCode.LANGUAGE_MISMATCH,
                HardFilterCode.GEOGRAPHY_MISMATCH,
                HardFilterCode.WORK_MODE_MISMATCH,
            },
        )
        self.assertTrue(
            all(failure.opportunity_value is not None for failure in decision.failures)
        )

    def test_source_languages_are_separate_profile_routing_constraint(self):
        ru_source_profile = _profile(
            preferences=_preferences(
                languages=("English",),
                source_languages=("ru",),
            )
        )
        opportunity = _opportunity(
            analysis=_analysis(language="English"),
            source_language="en",
        )

        decision = evaluate_hard_filters(opportunity, ru_source_profile)

        self.assertFalse(decision.eligible)
        self.assertEqual(
            _failure_codes(decision),
            {HardFilterCode.SOURCE_LANGUAGE_MISMATCH},
        )

    def test_known_source_language_matrix(self):
        cases = (
            ("ru", ("ru",), True, None),
            ("ru", ("en",), False, HardFilterCode.SOURCE_LANGUAGE_MISMATCH),
            ("ru", ("ru", "en"), True, None),
            ("en", ("en",), True, None),
            ("en", ("ru",), False, HardFilterCode.SOURCE_LANGUAGE_MISMATCH),
            ("en", ("ru", "en"), True, None),
        )
        for source_language, selected, expected_eligible, expected_reason in cases:
            with self.subTest(source_language=source_language, selected=selected):
                decision = evaluate_hard_filters(
                    _opportunity(source_language=source_language),
                    _profile(preferences=_preferences(source_languages=selected)),
                )

                self.assertEqual(decision.eligible, expected_eligible)
                if expected_reason is None:
                    self.assertEqual(decision.failures, ())
                else:
                    self.assertEqual(_failure_codes(decision), {expected_reason})

    def test_unresolved_source_language_fails_closed_for_explicit_profiles(self):
        ru_only = _profile(preferences=_preferences(source_languages=("ru",)))
        en_only = _profile(preferences=_preferences(source_languages=("en",)))
        ru_en = _profile(preferences=_preferences(source_languages=("ru", "en")))
        legacy = _profile(preferences=_preferences(source_languages=None))
        opportunity = _opportunity(source_language=None)

        ru_only_decision = evaluate_hard_filters(opportunity, ru_only)
        en_only_decision = evaluate_hard_filters(opportunity, en_only)
        ru_en_decision = evaluate_hard_filters(opportunity, ru_en)
        legacy_decision = evaluate_hard_filters(opportunity, legacy)

        self.assertFalse(ru_only_decision.eligible)
        self.assertFalse(en_only_decision.eligible)
        self.assertFalse(ru_en_decision.eligible)
        self.assertEqual(
            _failure_codes(ru_only_decision),
            {HardFilterCode.SOURCE_LANGUAGE_UNRESOLVED},
        )
        self.assertEqual(
            _failure_codes(en_only_decision),
            {HardFilterCode.SOURCE_LANGUAGE_UNRESOLVED},
        )
        self.assertEqual(
            _failure_codes(ru_en_decision),
            {HardFilterCode.SOURCE_LANGUAGE_UNRESOLVED},
        )
        self.assertTrue(legacy_decision.eligible)

    def test_unknown_opportunity_fields_are_nonblocking_and_never_fabricated(self):
        profile = _profile(
            preferences=_preferences(
                work_types=(),
                languages=(),
                geographies=(),
                work_modes=(),
                excluded_categories=("Adult",),
                budget_policy=BudgetPolicy.ALLOW_UNKNOWN,
            )
        )
        opportunity = _opportunity(
            analysis=_analysis(
                opportunity_type="unknown",
                category=None,
                language=None,
                location=None,
                remote=None,
                skills=(),
                role_title=None,
            )
        )

        decision = evaluate_hard_filters(opportunity, profile)

        self.assertTrue(decision.eligible)
        self.assertEqual(
            set(decision.nonblocking_unknowns),
            {
                UnknownMatchField.OPPORTUNITY_TYPE,
                UnknownMatchField.CATEGORY,
                UnknownMatchField.LANGUAGE,
                UnknownMatchField.GEOGRAPHY,
                UnknownMatchField.WORK_MODE,
                UnknownMatchField.BUDGET,
            },
        )

    def test_known_unsupported_opportunity_type_does_not_bypass_selection(self):
        profile = _profile(
            preferences=_preferences(
                work_types=(OpportunityType.PROJECT,),
            )
        )
        consultation = _opportunity(
            analysis=_analysis(opportunity_type="consultation")
        )

        decision = evaluate_hard_filters(consultation, profile)

        self.assertEqual(
            _failure_codes(decision),
            {HardFilterCode.WORK_TYPE_MISMATCH},
        )
        self.assertNotIn(
            UnknownMatchField.OPPORTUNITY_TYPE,
            decision.nonblocking_unknowns,
        )

    def test_candidate_trace_reduces_large_fixture_before_semantic_scoring(self):
        relevant = tuple(
            _profile(
                skills=("Python",),
                categories=("Telegram",),
                preferences=_preferences(
                    work_types=(OpportunityType.PROJECT,),
                    languages=("English",),
                    geographies=("Berlin",),
                    work_modes=(WorkMode.REMOTE,),
                ),
            )
            for _ in range(8)
        )
        unrelated = tuple(
            _profile(
                roles=(f"Designer {index}",),
                skills=(f"Figma {index}",),
                categories=(f"Design {index}",),
                preferences=_preferences(
                    work_types=(OpportunityType.VACANCY,),
                    languages=("Deutsch",),
                    geographies=("Munich",),
                ),
            )
            for index in range(192)
        )
        opportunity = _opportunity(
            analysis=_analysis(
                opportunity_type="project",
                category="Telegram",
                role_title="Python developer",
                skills=("Python",),
                language="English",
                location="Berlin",
                remote=True,
            )
        )

        result = narrow_and_filter_candidates(opportunity, relevant + unrelated)

        self.assertEqual(result.trace.active_profile_count, 200)
        self.assertEqual(result.trace.narrowed_candidate_count, 8)
        self.assertEqual(result.trace.hard_filter_eligible_count, 8)
        self.assertEqual(result.trace.semantic_score_candidate_count, 8)
        self.assertEqual(len(result.eligible_profiles), 8)
        self.assertEqual(
            set(result.trace.narrowing_dimensions),
            {
                "category_role_skills",
                "work_type",
                "language",
                "source_language",
                "geography",
            },
        )
        self.assertEqual(
            {exclusion.code for exclusion in result.trace.exclusions},
            {CandidateExclusionCode.WORK_TYPE_MISMATCH},
        )

    def test_hard_constraints_block_semantically_similar_profiles_before_scoring(self):
        excluded = _profile(
            preferences=_preferences(
                work_types=(OpportunityType.PROJECT,),
                geographies=("Berlin",),
                excluded_categories=("Telegram",),
            )
        )
        disabled_type = _profile(
            preferences=_preferences(
                work_types=(OpportunityType.VACANCY,),
                geographies=("Berlin",),
            )
        )
        wrong_geography = _profile(
            preferences=_preferences(
                work_types=(OpportunityType.PROJECT,),
                geographies=("Paris",),
            )
        )
        opportunity = _opportunity()

        result = narrow_and_filter_candidates(
            opportunity,
            (excluded, disabled_type, wrong_geography),
        )

        self.assertEqual(result.trace.active_profile_count, 3)
        self.assertEqual(result.trace.narrowed_candidate_count, 1)
        self.assertEqual(result.trace.semantic_score_candidate_count, 0)
        self.assertEqual(result.eligible_profiles, ())
        self.assertEqual(
            _failure_codes(result.decisions[0]),
            {HardFilterCode.EXCLUDED_CATEGORY},
        )
        self.assertEqual(
            {exclusion.code for exclusion in result.trace.exclusions},
            {
                CandidateExclusionCode.WORK_TYPE_MISMATCH,
                CandidateExclusionCode.GEOGRAPHY_MISMATCH,
            },
        )

    def test_non_active_opportunity_and_profile_never_enter_scoring(self):
        profile = _profile()
        stale = replace(
            _opportunity(),
            lifecycle_status=OpportunityLifecycleStatus.STALE,
        )
        inactive_profile = replace(profile, id=uuid4(), is_active=False)

        result = narrow_and_filter_candidates(stale, (profile, inactive_profile))

        self.assertFalse(result.opportunity_eligible)
        self.assertEqual(result.trace.active_profile_count, 1)
        self.assertEqual(result.trace.semantic_score_candidate_count, 0)
        self.assertEqual(result.eligible_profiles, ())


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not configured")
class CandidateMatchingPostgresTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.database_context = temporary_database()
        self.database_url = self.database_context.__enter__()
        migrate_to_head(self.database_url)
        self.database = Database(self.database_url)
        self.profiles = ProfileConfirmationService(self.database)

    async def asyncTearDown(self):
        await self.database.close()
        self.database_context.__exit__(None, None, None)

    async def test_service_reads_only_confirmed_active_profiles_from_postgres(self):
        active = await self._active_profile("active", skill="Python")
        inactive = await self._confirmed_profile("inactive", skill="Python")
        unrelated = await self._active_profile(
            "unrelated",
            role="Website chatbot developer",
            skill="JavaScript",
            category="Website chatbot",
        )
        opportunity_id = uuid4()
        async with self.database.transaction() as connection:
            raw_message_id = await _insert_known_source_message(
                connection,
                opportunity_id=opportunity_id,
            )
            await connection.execute(
                opportunities.insert().values(
                    id=opportunity_id,
                    schema_version=CANONICAL_OPPORTUNITY_SCHEMA_VERSION,
                    canonical_title="Python developer",
                    task_summary="Build a Telegram bot",
                    market_direction="buyer_to_specialist",
                    intent_stage="active",
                    opportunity_type="project",
                    category="Telegram",
                    role_title="Python developer",
                    skills=["Python"],
                    budget_known=False,
                    budget_explicit=False,
                    work_remote=True,
                    work_location=None,
                    work_full_time=None,
                    work_part_time=None,
                    language=None,
                    contact_telegram=None,
                    contact_email=None,
                    contact_url=None,
                    analysis_confidence=Decimal("0.9"),
                    quality_actionability=Decimal("0.8"),
                    quality_commercial_plausibility=Decimal("0.8"),
                    quality_specificity=Decimal("0.8"),
                    quality_credibility=Decimal("0.8"),
                    red_flags=[],
                    first_seen_at=NOW,
                    last_seen_at=NOW,
                    lifecycle_status="active",
                    lifecycle_changed_at=NOW,
                    preferred_raw_message_id=raw_message_id,
                    preferred_source_policy_version=PREFERRED_SOURCE_POLICY_VERSION,
                )
            )
            await connection.execute(
                opportunity_source_messages.insert().values(
                    raw_message_id=raw_message_id,
                    opportunity_id=opportunity_id,
                )
            )

        service = CandidateMatchingService(self.database)
        result = await service.candidates_for_opportunity(opportunity_id)
        scoring = await service.structured_scores_for_opportunity(opportunity_id)
        semantic = await service.semantic_scores_for_opportunity(opportunity_id)
        generated = await service.generate_matches(
            (opportunity_id,),
            evaluated_at=NOW,
        )
        traces_by_profile = {
            record.trace.search_profile_id: record.trace
            for record in generated.persistence.traces
        }

        self.assertEqual(result.trace.active_profile_count, 2)
        self.assertEqual(result.trace.narrowed_candidate_count, 2)
        self.assertEqual(
            {profile.id for profile in result.eligible_profiles},
            {active.profile.id, unrelated.profile.id},
        )
        self.assertNotIn(inactive.profile.id, traces_by_profile)
        self.assertEqual(len(scoring.scores), 2)
        self.assertEqual(
            {score.profile_id for score in scoring.scores},
            {active.profile.id, unrelated.profile.id},
        )
        self.assertTrue(
            all(score.source_quality_score is None for score in scoring.scores)
        )
        self.assertEqual(
            scoring.candidates.trace.semantic_score_candidate_count,
            2,
        )
        self.assertEqual(len(semantic.scores), 2)
        self.assertEqual(
            {score.structured.profile_id for score in semantic.scores},
            {active.profile.id, unrelated.profile.id},
        )
        self.assertEqual(semantic.status.value, "available")
        self.assertEqual(generated.report.candidate_pair_count, 2)
        self.assertEqual(generated.report.eligible_match_count, 1)
        self.assertTrue(traces_by_profile[active.profile.id].eligible)
        unrelated_trace = traces_by_profile[unrelated.profile.id]
        self.assertTrue(unrelated_trace.hard_filter_eligible)
        self.assertEqual(unrelated_trace.hard_filter_reasons, ())
        self.assertFalse(unrelated_trace.eligible)
        self.assertIn(
            "narrowing.no_structured_target_overlap",
            {reason["code"] for reason in unrelated_trace.narrowing_diagnostics},
        )
        self.assertIn(
            CandidateExclusionCode.NO_STRUCTURED_TARGET_OVERLAP,
            {
                exclusion.code
                for exclusion in result.trace.exclusions
                if exclusion.profile_id == unrelated.profile.id
            },
        )

    async def test_explicit_ru_en_profile_rejects_db_backed_unresolved_source_language(self):
        active = await self._active_profile(
            "explicit-ru-en-unresolved",
            skill="Python",
            source_languages=("ru", "en"),
        )
        opportunity_id = uuid4()
        async with self.database.transaction() as connection:
            raw_message_id = await _insert_known_source_message(
                connection,
                opportunity_id=opportunity_id,
                source_language=None,
            )
            await connection.execute(
                opportunities.insert().values(
                    id=opportunity_id,
                    schema_version=CANONICAL_OPPORTUNITY_SCHEMA_VERSION,
                    canonical_title="Python developer",
                    task_summary="Build a Telegram bot",
                    market_direction="buyer_to_specialist",
                    intent_stage="active",
                    opportunity_type="project",
                    category="Telegram",
                    role_title="Python developer",
                    skills=["Python"],
                    budget_known=False,
                    budget_explicit=False,
                    work_remote=True,
                    work_location=None,
                    work_full_time=None,
                    work_part_time=None,
                    language=None,
                    contact_telegram=None,
                    contact_email=None,
                    contact_url=None,
                    analysis_confidence=Decimal("0.9"),
                    quality_actionability=Decimal("0.8"),
                    quality_commercial_plausibility=Decimal("0.8"),
                    quality_specificity=Decimal("0.8"),
                    quality_credibility=Decimal("0.8"),
                    red_flags=[],
                    first_seen_at=NOW,
                    last_seen_at=NOW,
                    lifecycle_status="active",
                    lifecycle_changed_at=NOW,
                    preferred_raw_message_id=raw_message_id,
                    preferred_source_policy_version=PREFERRED_SOURCE_POLICY_VERSION,
                )
            )
            await connection.execute(
                opportunity_source_messages.insert().values(
                    raw_message_id=raw_message_id,
                    opportunity_id=opportunity_id,
                )
            )

        service = CandidateMatchingService(self.database)
        generated = await service.generate_matches(
            (opportunity_id,),
            evaluated_at=NOW,
        )
        self.assertEqual(generated.report.candidate_pair_count, 1)
        self.assertEqual(generated.report.eligible_match_count, 0)
        self.assertEqual(generated.report.hard_rejected_count, 1)
        trace = generated.persistence.traces[0].trace
        self.assertEqual(trace.search_profile_id, active.profile.id)
        self.assertFalse(trace.hard_filter_eligible)
        self.assertFalse(trace.eligible)
        self.assertEqual(
            {reason["code"] for reason in trace.hard_filter_reasons},
            {"source_language_unresolved"},
        )
        self.assertTrue(
            {
                "routing.source_language_unresolved",
                "narrowing.source_language_unresolved",
            }
            & {reason["code"] for reason in trace.narrowing_diagnostics},
        )

    async def _confirmed_profile(
        self,
        user: str,
        *,
        role: str = "Developer",
        skill: str,
        category: str = "Telegram",
    ):
        draft = await self.profiles.create_manual_draft(
            platform="telegram",
            external_user_id=user,
            semantic_text=f"{role} | {skill} | {category}",
            roles=(role,),
            skills=(skill,),
            categories=(category,),
        )
        return await self.profiles.confirm(
            platform="telegram",
            external_user_id=user,
            profile_id=draft.profile.id,
            expected_revision=draft.profile.revision,
        )

    async def _active_profile(
        self,
        user: str,
        *,
        role: str = "Developer",
        skill: str,
        category: str = "Telegram",
        source_languages: tuple[str, ...] | None = None,
    ):
        confirmed = await self._confirmed_profile(
            user,
            role=role,
            skill=skill,
            category=category,
        )
        activated = await self.profiles.activate(
            platform="telegram",
            external_user_id=user,
            profile_id=confirmed.profile.id,
            expected_revision=confirmed.profile.revision,
        )
        if source_languages is not None:
            return await self.profiles.set_source_languages(
                platform="telegram",
                external_user_id=user,
                profile_id=activated.profile.profile.id,
                source_languages=source_languages,
                expected_revision=activated.profile.profile.revision,
            )
        return activated.profile


def _profile(
    *,
    roles=("Developer",),
    skills=("Python",),
    categories=("Telegram",),
    preferences=None,
) -> SearchProfileRecord:
    parsed = parse_search_profile(
        roles=roles,
        skills=skills,
        categories=categories,
        semantic_text="Developer building Telegram products",
    )
    return SearchProfileRecord(
        id=uuid4(),
        user_id=uuid4(),
        schema_version=parsed.schema_version,
        parser_version=parsed.parser_version,
        analysis_cache_id=None,
        roles=parsed.roles,
        skills=parsed.skills,
        categories=parsed.categories,
        semantic_text_original=parsed.semantic_text_original,
        semantic_text_normalized=parsed.semantic_text_normalized,
        preferences=preferences or _preferences(),
        confirmation_status=SearchProfileConfirmationStatus.CONFIRMED,
        revision=1,
        confirmed_at=NOW,
        is_active=True,
        is_primary=False,
        activated_at=NOW,
        deactivated_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


def _preferences(**overrides):
    values = {
        "work_types": None,
        "minimum_budget": None,
        "currency": None,
        "budget_policy": None,
        "languages": None,
        "geographies": None,
        "work_modes": None,
        "excluded_categories": None,
        "source_languages": None,
    }
    values.update(overrides)
    return parse_search_profile_preferences(**values)


async def _insert_known_source_message(
    connection,
    *,
    opportunity_id,
    source_language="en",
):
    raw_message_id = uuid4()
    raw_job_id = uuid4()
    correlation_id = uuid4()
    source_key = opportunity_id.hex
    collector_account_id = await connection.scalar(
        collector_accounts.insert()
        .values(
            platform="telegram",
            external_account_id=f"matching-filters:{source_key}",
            display_name="Matching filters fixture collector",
        )
        .returning(collector_accounts.c.id)
    )
    source_id = await connection.scalar(
        sources.insert()
        .values(
            platform="telegram",
            external_id=f"username:matching_filters_{source_key}",
            access_type="public",
            lifecycle_status="approved",
            display_name="Matching filters fixture source",
            handle=f"@matching_filters_{source_key[:15]}",
            canonical_url=f"https://t.me/matching_filters_{source_key}",
            language=source_language,
            language_origin=None if source_language is None else "seed",
        )
        .returning(sources.c.id)
    )
    await connection.execute(
        durable_jobs.insert().values(
            id=raw_job_id,
            job_type="telegram.raw_message.v1",
            idempotency_key=f"matching-filters-fixture:{source_key}",
            correlation_id=correlation_id,
        )
    )
    await connection.execute(
        raw_messages.insert().values(
            id=raw_message_id,
            source_id=source_id,
            collector_account_id=collector_account_id,
            processing_job_id=raw_job_id,
            schema_version="telegram.raw_message.v1",
            platform="telegram",
            external_source_id=f"username:matching_filters_{source_key}",
            external_message_id=42,
            message_date=NOW,
            observed_at=NOW,
            message_url=f"https://t.me/matching_filters_{source_key}/42",
            content="Build a Telegram bot",
            transport_metadata={},
            ingestion_origin="live",
            correlation_id=correlation_id,
        )
    )
    return raw_message_id


def _opportunity(
    *,
    analysis=None,
    budget=None,
    source_language="en",
) -> CanonicalOpportunityRecord:
    selected_analysis = analysis or _analysis(budget=budget)
    preferred_source = _source_observation(language=source_language)
    return CanonicalOpportunityRecord(
        id=uuid4(),
        schema_version=CANONICAL_OPPORTUNITY_SCHEMA_VERSION,
        canonical_title=selected_analysis.role_title,
        task_summary=selected_analysis.task_summary,
        analysis=selected_analysis,
        first_seen_at=NOW,
        last_seen_at=NOW,
        lifecycle_status=OpportunityLifecycleStatus.ACTIVE,
        lifecycle_changed_at=NOW,
        raw_message_ids=(),
        analysis_cache_ids=(),
        analysis_links=(),
        preferred_source_policy_version=None,
        preferred_source=preferred_source,
        source_observations=(preferred_source,),
        lifecycle_events=(),
        created_at=NOW,
        updated_at=NOW,
    )


def _source_observation(*, language="en") -> OpportunitySourceObservationRecord:
    return OpportunitySourceObservationRecord(
        raw_message_id=uuid4(),
        source_id=42,
        platform="telegram",
        external_source_id="username:source_fixture",
        source_display_name="Source fixture",
        source_handle="@source_fixture",
        source_canonical_url="https://t.me/source_fixture",
        source_language=language,
        source_language_origin=None if language is None else "seed",
        message_url="https://t.me/source_fixture/1",
        message_date=NOW,
        observed_at=NOW,
        linked_at=NOW,
        is_preferred=True,
    )


def _analysis(
    *,
    opportunity_type="project",
    category="Telegram",
    role_title="Python developer",
    skills=("Python",),
    language="English",
    location="Berlin",
    remote=True,
    budget=None,
) -> OpportunityAnalysis:
    return OpportunityAnalysis.model_validate_json(
        json.dumps(
            {
                "schema_version": "opportunity_analysis.v1",
                "is_opportunity": True,
                "confidence": 0.9,
                "market_direction": "buyer_to_specialist",
                "intent_stage": "active",
                "opportunity_type": opportunity_type,
                "category": category,
                "role_title": role_title,
                "skills": skills,
                "task_summary": "Build a Telegram bot",
                "budget": budget or _budget(known=False, explicit=False),
                "work": {
                    "remote": remote,
                    "location": location,
                    "full_time": None,
                    "part_time": None,
                },
                "language": language,
                "contact": {"telegram": None, "email": None, "url": None},
                "quality": {
                    "actionability": 0.8,
                    "commercial_plausibility": 0.8,
                    "specificity": 0.8,
                    "credibility": 0.8,
                },
                "red_flags": (),
            }
        )
    )


def _budget(
    *,
    known,
    explicit,
    minimum=None,
    maximum=None,
    currency=None,
):
    return {
        "known": known,
        "min": minimum,
        "max": maximum,
        "currency": currency,
        "period": None,
        "explicit": explicit,
    }


def _failure_codes(decision):
    return {failure.code for failure in decision.failures}


if __name__ == "__main__":
    unittest.main()
