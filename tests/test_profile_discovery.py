from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa

from freelancer_bot import operator_cli
from freelancer_bot.discovery import DiscoveryRequest
from freelancer_bot.persistence.database import Database
from freelancer_bot.persistence.schema import (
    discovery_runs,
    profile_discovery_intents,
    source_profile_relevance,
    sources,
)
from freelancer_bot.persistence.discovery import (
    DiscoveryRunConflict,
    DiscoveryRunRepository,
)
from freelancer_bot.profile_discovery import (
    DiscoveryProfileInput,
    PROFILE_DISCOVERY_INTENT_VERSION,
    ProfileDiscoveryIntent,
    ProfileDiscoveryIntentRepository,
    ProfileDiscoveryService,
    build_discovery_intent,
    build_evaluation_intent,
    build_profile_discovery_intent,
    evaluation_profile_specs,
    evaluate_source_relevance,
    _effective_provider_observability,
    web_strategy_for_intent,
)
from freelancer_bot.profile_confirmation import ProfileConfirmationService
from freelancer_bot.web_discovery import (
    WebSearchResult,
    collapse_near_duplicate_queries,
)
from postgres_support import TEST_DATABASE_URL, migrate_to_head, temporary_database


NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)


class ProfileDiscoveryIntentTest(unittest.TestCase):
    def test_current_profile_discovery_intent_version_is_v2(self):
        self.assertEqual(
            PROFILE_DISCOVERY_INTENT_VERSION,
            "profile-discovery-intent.v2",
        )
        intent = build_discovery_intent(
            DiscoveryProfileInput(
                identity_key="unit-profile",
                search_profile_id=None,
                profile_revision=8,
                roles=("Python developer",),
                services=("Telegram bots",),
                skills=("Telethon",),
                industries=("automation",),
                languages=("en", "ru"),
                geographies=(),
                work_modes=("remote",),
            )
        )

        self.assertEqual(intent.version, "profile-discovery-intent.v2")

    def test_intent_identity_changes_across_contract_versions(self):
        profile = DiscoveryProfileInput(
            identity_key="profile:e3f2a0d1-3a46-4506-8a79-f4ed47400279",
            search_profile_id=None,
            profile_revision=8,
            roles=("Python developer",),
            services=("Telegram bots",),
            skills=("Telethon",),
            industries=("automation",),
            languages=("en", "ru"),
            geographies=(),
            work_modes=("remote",),
        )

        v1_id = uuid5(
            NAMESPACE_URL,
            f"profile-discovery-intent.v1:{profile.identity_key}:"
            f"{profile.profile_revision}",
        )
        first_v2 = build_discovery_intent(profile)
        second_v2 = build_discovery_intent(profile)

        self.assertNotEqual(v1_id, first_v2.id)
        self.assertEqual(first_v2.id, second_v2.id)
        self.assertEqual(first_v2.version, "profile-discovery-intent.v2")

    def test_effective_provider_observability_falls_back_when_run_lacks_observability(self):
        execution = SimpleNamespace(run=SimpleNamespace(request={}))
        provider = SimpleNamespace(
            observability={
                "queries_executable": 4,
                "queries_selected": 4,
                "query_limit": None,
            }
        )

        self.assertEqual(
            _effective_provider_observability(execution, provider),
            {
                "queries_executable": 4,
                "queries_selected": 4,
                "query_limit": None,
            },
        )

    def test_ten_evaluation_intents_are_deterministic_and_materially_distinct(self):
        specs = evaluation_profile_specs()
        intents = [build_evaluation_intent(spec) for spec in specs]

        self.assertEqual(len(specs), 10)
        self.assertEqual(len({intent.id for intent in intents}), 10)
        self.assertEqual(
            len({intent.literal_concepts for intent in intents}),
            10,
        )
        expected_role_terms = (
            ("Python developer", "backend developer", "Telegram bot developer"),
            ("Product Designer", "UX/UI Designer"),
            ("Graphic Designer", "Brand Designer"),
            ("SMM Manager", "Social Media Manager", "Performance Marketer"),
            ("Video Editor", "Motion Designer"),
            ("Photographer", "Content Creator", "UGC Creator"),
            ("Copywriter", "Content Writer", "Content Manager"),
            ("Recruiter", "Talent Acquisition", "HR"),
            ("Sales Manager", "Business Development Manager"),
            ("Marketplace Manager", "E-commerce Specialist"),
        )
        for spec, expected in zip(specs, expected_role_terms):
            self.assertEqual(spec.roles, expected)
        for intent in intents:
            strategy = web_strategy_for_intent(intent)
            queries = strategy.build_queries(
                DiscoveryRequest(parameters={}, requested_at=NOW)
            )
            self.assertGreaterEqual(len(queries), 10)
            self.assertTrue(any(query.angle == "direct" for query in queries))
            self.assertTrue(any(query.angle == "buyer_habitat" for query in queries))
            self.assertTrue(any(query.angle == "adjacent" for query in queries))
            self.assertTrue(intent.generated_web_queries)
            self.assertTrue(intent.likely_buyer_roles)
            self.assertTrue(intent.buyer_habitats)

    def test_relevance_is_explainable_and_does_not_make_irrelevant_sources_strong(self):
        intent = build_evaluation_intent(evaluation_profile_specs()[0])
        relevant_source = SimpleNamespace(
            id=11,
            platform="telegram",
            external_id="username:python_buyers",
            display_name="Python Telegram Bots Automation Buyers",
        )
        relevant_lineage = SimpleNamespace(
            context={
                "matches": [
                    {
                        "topic": "Python developer hiring communities",
                        "query_angle": "buyer_habitat",
                        "query": "site:t.me python developer",
                    },
                    {
                        "topic": "Telethon implementation",
                        "query_angle": "direct",
                    },
                ]
            }
        )
        relevant = evaluate_source_relevance(intent, relevant_source, (relevant_lineage,))
        irrelevant = evaluate_source_relevance(
            intent,
            SimpleNamespace(
                id=12,
                platform="telegram",
                external_id="username:cooking",
                display_name="Home Cooking Recipes",
            ),
            (),
        )

        self.assertEqual(relevant.relevance_class, "strong")
        self.assertIn("direct_concept", relevant.evidence_categories)
        self.assertIn("buyer_habitat", relevant.evidence_categories)
        self.assertEqual(irrelevant.relevance_class, "weak")

    def test_generic_buyer_habitat_never_becomes_high_without_support(self):
        intent = build_evaluation_intent(evaluation_profile_specs()[0])
        generic = evaluate_source_relevance(
            intent,
            SimpleNamespace(
                id=13,
                platform="telegram",
                external_id="username:generic_business",
                display_name="Founders and Operators Community",
            ),
            (
                SimpleNamespace(
                    context={
                        "matches": [
                            {
                                "topic": "founder and operator communities",
                                "query_angle": "buyer_habitat",
                            }
                        ]
                    }
                ),
            ),
        )

        self.assertNotEqual(generic.relevance_class, "strong")
        self.assertEqual(generic.explanation.semantic_category, "generic_business")
        self.assertEqual(generic.explanation.diagnostic_label, "WEAK")
        self.assertNotIn("direct_concept", generic.evidence_categories)


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not configured")
class ProfileDiscoveryPostgresIntegrationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.database_context = temporary_database()
        self.database_url = self.database_context.__enter__()
        migrate_to_head(self.database_url)
        self.database = Database(self.database_url, pool_size=4, max_overflow=8)

    async def asyncTearDown(self):
        await self.database.close()
        self.database_context.__exit__(None, None, None)

    async def _active_python_profile(self, external_user_id: str):
        confirmation = ProfileConfirmationService(self.database)
        draft = await confirmation.create_manual_draft(
            platform="telegram",
            external_user_id=external_user_id,
            semantic_text="Python Telegram automation",
            roles=("Python developer",),
            skills=("Telethon", "PostgreSQL"),
            categories=("Telegram bots",),
        )
        confirmed = await confirmation.confirm(
            platform="telegram",
            external_user_id=external_user_id,
            profile_id=draft.profile.id,
            expected_revision=draft.profile.revision,
        )
        activated = await confirmation.activate(
            platform="telegram",
            external_user_id=external_user_id,
            profile_id=draft.profile.id,
            expected_revision=confirmed.profile.revision,
        )
        return activated.profile.profile

    def _legacy_v1_intent(self, current: ProfileDiscoveryIntent) -> ProfileDiscoveryIntent:
        legacy_queries = tuple(
            f"legacy-v1 {query}" for query in current.generated_web_queries
        )
        return ProfileDiscoveryIntent(
            **{
                **current.__dict__,
                "id": uuid5(
                    NAMESPACE_URL,
                    f"profile-discovery-intent.v1:{current.search_profile_id}:"
                    f"{current.profile_revision}",
                ),
                "generated_web_queries": legacy_queries,
                "version": "profile-discovery-intent.v1",
            }
        )

    async def test_legacy_v1_intent_coexists_with_current_v2_discovery(self):
        profile = await self._active_python_profile(
            "profile-discovery-legacy-v1-owner"
        )
        current_v2 = build_profile_discovery_intent(profile)
        legacy_v1 = self._legacy_v1_intent(current_v2)
        repository = ProfileDiscoveryIntentRepository()
        async with self.database.transaction() as connection:
            legacy_outcome = await repository.ensure(connection, legacy_v1)
        self.assertTrue(legacy_outcome.created)

        class Backend:
            def __init__(self):
                self.calls = []

            async def search(self, query, *, language, limit):
                self.calls.append((query, language, limit))
                return (
                    WebSearchResult(
                        "https://t.me/python_v2_buyers/1",
                        "Python Telegram Automation Buyers",
                        "Need a Telethon implementation partner",
                    ),
                )

        backend = Backend()
        service = ProfileDiscoveryService(self.database)
        execution = await service.discover_profile(
            profile,
            requested_at=NOW,
            run_key="profile-discovery-v1-then-v2-v1",
            backend=backend,
            max_queries=12,
        )

        async with self.database.connect() as connection:
            rows = (
                await connection.execute(
                    sa.select(profile_discovery_intents)
                    .where(profile_discovery_intents.c.search_profile_id == profile.id)
                    .where(
                        profile_discovery_intents.c.profile_revision
                        == profile.revision
                    )
                    .order_by(profile_discovery_intents.c.version)
                )
            ).mappings().all()
            run = await DiscoveryRunRepository().get_by_key(
                connection,
                provider="web_search",
                run_key="profile-discovery-v1-then-v2-v1",
            )

        self.assertEqual(execution.intent.version, "profile-discovery-intent.v2")
        self.assertEqual(execution.intent.id, current_v2.id)
        self.assertNotEqual(legacy_v1.id, current_v2.id)
        self.assertEqual(len(rows), 2)
        by_version = {row["version"]: row for row in rows}
        self.assertEqual(
            set(by_version),
            {"profile-discovery-intent.v1", "profile-discovery-intent.v2"},
        )
        self.assertEqual(by_version["profile-discovery-intent.v1"]["id"], legacy_v1.id)
        self.assertEqual(
            tuple(by_version["profile-discovery-intent.v1"]["generated_web_queries"]),
            legacy_v1.generated_web_queries,
        )
        self.assertEqual(by_version["profile-discovery-intent.v2"]["id"], current_v2.id)
        self.assertEqual(
            run.request["parameters"]["profile_discovery"]["intent_id"],
            str(current_v2.id),
        )
        self.assertEqual(
            run.request["parameters"]["profile_discovery"]["intent_version"],
            "profile-discovery-intent.v2",
        )
        self.assertEqual(len(backend.calls), 12)

    async def test_current_v2_intent_conflict_still_fails_closed(self):
        profile = await self._active_python_profile(
            "profile-discovery-v2-conflict-owner"
        )
        current_v2 = build_profile_discovery_intent(profile)
        conflicting_v2 = ProfileDiscoveryIntent(
            **{
                **current_v2.__dict__,
                "generated_web_queries": (
                    "conflicting generated query",
                    *current_v2.generated_web_queries[1:],
                ),
            }
        )
        repository = ProfileDiscoveryIntentRepository()

        async with self.database.transaction() as connection:
            first = await repository.ensure(connection, current_v2)
            self.assertTrue(first.created)
            with self.assertRaisesRegex(
                RuntimeError,
                "profile discovery intent identity has conflicting content",
            ):
                await repository.ensure(connection, conflicting_v2)

    async def test_activation_persists_one_intent_and_web_discovery_is_idempotent(self):
        confirmation = ProfileConfirmationService(self.database)
        draft = await confirmation.create_manual_draft(
            platform="telegram",
            external_user_id="profile-discovery-owner",
            semantic_text="Python Telegram automation",
            roles=("Python developer",),
            skills=("Telethon", "PostgreSQL"),
            categories=("Telegram bots",),
        )
        confirmed = await confirmation.confirm(
            platform="telegram",
            external_user_id="profile-discovery-owner",
            profile_id=draft.profile.id,
            expected_revision=draft.profile.revision,
        )
        activated = await confirmation.activate(
            platform="telegram",
            external_user_id="profile-discovery-owner",
            profile_id=draft.profile.id,
            expected_revision=confirmed.profile.revision,
        )

        class Backend:
            def __init__(self):
                self.calls = 0

            async def search(self, query, *, language, limit):
                self.calls += 1
                return (
                    WebSearchResult(
                        "https://t.me/python_automation_buyers/1",
                        "Python Telegram Automation Buyers",
                        "Need a Telethon implementation partner",
                    ),
                )

        backend = Backend()
        service = ProfileDiscoveryService(self.database)
        first = await service.discover_profile(
            activated.profile.profile,
            requested_at=NOW,
            run_key="profile-discovery-integration-v1",
            backend=backend,
        )
        second = await service.discover_profile(
            activated.profile.profile,
            requested_at=NOW,
            run_key="profile-discovery-integration-v1",
            backend=backend,
        )

        async with self.database.connect() as connection:
            intent_count = await connection.scalar(
                sa.select(sa.func.count()).select_from(profile_discovery_intents)
            )
            relevance_count = await connection.scalar(
                sa.select(sa.func.count()).select_from(source_profile_relevance)
            )
            source_count = await connection.scalar(
                sa.select(sa.func.count()).select_from(sources)
            )
            run_count = await connection.scalar(
                sa.select(sa.func.count())
                .select_from(discovery_runs)
                .where(discovery_runs.c.run_key == "profile-discovery-integration-v1")
            )

        self.assertTrue(activated.profile.profile.is_active)
        self.assertEqual(intent_count, 1)
        self.assertEqual(relevance_count, 1)
        self.assertEqual(source_count, 1)
        self.assertEqual(run_count, 1)
        self.assertEqual(first.new_candidates, 1)
        self.assertEqual(second.unique_candidates, 1)
        queries = web_strategy_for_intent(first.intent).build_queries(
            DiscoveryRequest(parameters={}, requested_at=NOW)
        )
        self.assertEqual(
            backend.calls,
            len(collapse_near_duplicate_queries(queries).queries),
        )

    async def test_profile_web_discovery_persists_with_bounded_query_execution(self):
        confirmation = ProfileConfirmationService(self.database)
        draft = await confirmation.create_manual_draft(
            platform="telegram",
            external_user_id="profile-discovery-owner",
            semantic_text="Python Telegram automation",
            roles=("Python developer",),
            skills=("Telethon", "PostgreSQL"),
            categories=("Telegram bots",),
        )
        confirmed = await confirmation.confirm(
            platform="telegram",
            external_user_id="profile-discovery-owner",
            profile_id=draft.profile.id,
            expected_revision=draft.profile.revision,
        )
        activated = await confirmation.activate(
            platform="telegram",
            external_user_id="profile-discovery-owner",
            profile_id=draft.profile.id,
            expected_revision=confirmed.profile.revision,
        )

        class Backend:
            def __init__(self):
                self.calls = []

            async def search(self, query, *, language, limit):
                self.calls.append((query, language, limit))
                return (
                    WebSearchResult(
                        "https://t.me/python_bounded_buyers/1",
                        "Python Telegram Automation Buyers",
                        "Need a Telethon implementation partner",
                    ),
                )

        backend = Backend()
        service = ProfileDiscoveryService(self.database)
        first = await service.discover_profile(
            activated.profile.profile,
            requested_at=NOW,
            run_key="profile-discovery-bounded-integration-v1",
            backend=backend,
            max_queries=12,
        )
        second = await service.discover_profile(
            activated.profile.profile,
            requested_at=NOW,
            run_key="profile-discovery-bounded-integration-v1",
            backend=backend,
            max_queries=12,
        )

        async with self.database.connect() as connection:
            intent_count = await connection.scalar(
                sa.select(sa.func.count()).select_from(profile_discovery_intents)
            )
            relevance_count = await connection.scalar(
                sa.select(sa.func.count()).select_from(source_profile_relevance)
            )
            source_count = await connection.scalar(
                sa.select(sa.func.count()).select_from(sources)
            )
            run_count = await connection.scalar(
                sa.select(sa.func.count())
                .select_from(discovery_runs)
                .where(
                    discovery_runs.c.run_key
                    == "profile-discovery-bounded-integration-v1"
                )
            )
            run = await DiscoveryRunRepository().get_by_key(
                connection,
                provider="web_search",
                run_key="profile-discovery-bounded-integration-v1",
            )

        self.assertEqual(intent_count, 1)
        self.assertEqual(relevance_count, 1)
        self.assertEqual(source_count, 1)
        self.assertEqual(run_count, 1)
        self.assertEqual(first.new_candidates, 1)
        self.assertEqual(second.unique_candidates, 1)
        self.assertLessEqual(len(backend.calls), 12)
        self.assertEqual(len(backend.calls), 12)
        self.assertIn("observability", run.request)
        self.assertEqual(
            run.request["observability"]["queries_executable"],
            first.provider_observability["queries_executable"],
        )
        self.assertEqual(
            run.request["observability"]["queries_selected"],
            first.provider_observability["queries_selected"],
        )
        self.assertEqual(
            run.request["observability"]["queries_executed"],
            first.provider_observability["queries_executed"],
        )
        self.assertEqual(
            run.request["observability"]["query_limit"],
            first.provider_observability["query_limit"],
        )
        self.assertGreaterEqual(first.provider_observability["queries_executable"], 12)
        self.assertEqual(first.provider_observability["queries_selected"], 12)
        self.assertEqual(first.provider_observability["queries_executed"], 12)
        self.assertEqual(first.provider_observability["query_limit"], 12)
        self.assertEqual(
            sum(first.provider_observability["query_angle_counts"]["selected"].values()),
            12,
        )
        self.assertEqual(
            second.provider_observability["queries_executable"],
            first.provider_observability["queries_executable"],
        )
        self.assertEqual(
            second.provider_observability["queries_selected"],
            first.provider_observability["queries_selected"],
        )
        self.assertEqual(
            second.provider_observability["queries_executed"],
            first.provider_observability["queries_executed"],
        )
        self.assertEqual(second.provider_observability["query_limit"], 12)
        self.assertGreaterEqual(
            first.provider_observability["queries_executable"],
            first.provider_observability["queries_selected"],
        )
        fresh_payload = operator_cli._profile_execution_payload(first)
        reused_payload = operator_cli._profile_execution_payload(second)
        self.assertEqual(
            reused_payload["generated_query_count"],
            fresh_payload["generated_query_count"],
        )
        self.assertEqual(
            reused_payload["executable_query_count"],
            first.provider_observability["queries_executable"],
        )
        self.assertEqual(reused_payload["selected_query_count"], 12)
        self.assertEqual(reused_payload["executed_query_count"], 12)
        self.assertEqual(reused_payload["query_limit"], 12)
        self.assertEqual(
            reused_payload["selected_query_angle_counts"],
            fresh_payload["selected_query_angle_counts"],
        )
        for field in (
            "executable_query_count",
            "selected_query_count",
            "executed_query_count",
            "query_limit",
            "executable_query_angle_counts",
            "selected_query_angle_counts",
        ):
            self.assertEqual(reused_payload[field], fresh_payload[field])

    async def test_profile_web_discovery_run_key_includes_explicit_query_bound(self):
        confirmation = ProfileConfirmationService(self.database)
        draft = await confirmation.create_manual_draft(
            platform="telegram",
            external_user_id="profile-discovery-owner",
            semantic_text="Python Telegram automation",
            roles=("Python developer",),
            skills=("Telethon", "PostgreSQL"),
            categories=("Telegram bots",),
        )
        confirmed = await confirmation.confirm(
            platform="telegram",
            external_user_id="profile-discovery-owner",
            profile_id=draft.profile.id,
            expected_revision=draft.profile.revision,
        )
        activated = await confirmation.activate(
            platform="telegram",
            external_user_id="profile-discovery-owner",
            profile_id=draft.profile.id,
            expected_revision=confirmed.profile.revision,
        )
        profile = activated.profile.profile

        class Backend:
            def __init__(self):
                self.calls = []

            async def search(self, query, *, language, limit):
                self.calls.append(query)
                return (
                    WebSearchResult(
                        "https://t.me/python_run_key_buyers/1",
                        "Python Telegram Automation Buyers",
                        "Need a Telethon implementation partner",
                    ),
                )

        backend = Backend()
        service = ProfileDiscoveryService(self.database)
        await service.discover_profile(
            profile,
            requested_at=NOW,
            run_key="profile-discovery-bound-request-v1",
            backend=backend,
            max_queries=12,
        )
        calls_after_first = len(backend.calls)
        self.assertEqual(calls_after_first, 12)
        async with self.database.connect() as connection:
            run = await DiscoveryRunRepository().get_by_key(
                connection,
                provider="web_search",
                run_key="profile-discovery-bound-request-v1",
            )
        self.assertEqual(
            run.request["parameters"]["profile_discovery"]["max_queries"],
            12,
        )

        await service.discover_profile(
            profile,
            requested_at=NOW,
            run_key="profile-discovery-bound-request-v1",
            backend=backend,
            max_queries=12,
        )
        self.assertEqual(len(backend.calls), calls_after_first)

        with self.assertRaises(DiscoveryRunConflict):
            await service.discover_profile(
                profile,
                requested_at=NOW,
                run_key="profile-discovery-bound-request-v1",
                backend=backend,
                max_queries=6,
            )
        self.assertEqual(len(backend.calls), calls_after_first)

        with self.assertRaises(DiscoveryRunConflict):
            await service.discover_profile(
                profile,
                requested_at=NOW,
                run_key="profile-discovery-bound-request-v1",
                backend=backend,
                max_queries=None,
            )
        self.assertEqual(len(backend.calls), calls_after_first)

        unbounded_first = await service.discover_profile(
            profile,
            requested_at=NOW,
            run_key="profile-discovery-unbounded-request-v1",
            backend=backend,
            max_queries=None,
        )
        calls_after_unbounded = len(backend.calls)
        async with self.database.connect() as connection:
            unbounded = await DiscoveryRunRepository().get_by_key(
                connection,
                provider="web_search",
                run_key="profile-discovery-unbounded-request-v1",
            )
        self.assertNotIn(
            "max_queries",
            unbounded.request["parameters"]["profile_discovery"],
        )

        unbounded_second = await service.discover_profile(
            profile,
            requested_at=NOW,
            run_key="profile-discovery-unbounded-request-v1",
            backend=backend,
            max_queries=None,
        )
        self.assertEqual(len(backend.calls), calls_after_unbounded)
        self.assertIsNone(unbounded_second.provider_observability["query_limit"])
        self.assertEqual(
            unbounded_second.provider_observability["queries_executable"],
            unbounded_first.provider_observability["queries_executable"],
        )
        self.assertEqual(
            unbounded_second.provider_observability["queries_selected"],
            unbounded_first.provider_observability["queries_selected"],
        )

        with self.assertRaises(DiscoveryRunConflict):
            await service.discover_profile(
                profile,
                requested_at=NOW,
                run_key="profile-discovery-unbounded-request-v1",
                backend=backend,
                max_queries=12,
            )
        self.assertEqual(len(backend.calls), calls_after_unbounded)


if __name__ == "__main__":
    unittest.main()
