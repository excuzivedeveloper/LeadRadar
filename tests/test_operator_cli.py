import io
import sys
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault(
    "fcntl",
    SimpleNamespace(
        LOCK_EX=2,
        LOCK_NB=4,
        LOCK_UN=8,
        flock=lambda *args, **kwargs: None,
    ),
)

from freelancer_bot import operator_cli


class _AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class OperatorCliProfileDiscoveryTest(unittest.IsolatedAsyncioTestCase):
    def test_profile_discovery_run_parses_max_queries(self):
        args = operator_cli.build_parser().parse_args(
            [
                "profile-discovery",
                "run",
                "--profile-id",
                "11111111-1111-1111-1111-111111111111",
                "--searxng-url",
                "http://search.example.test",
                "--max-queries",
                "12",
            ]
        )

        self.assertEqual(args.max_queries, 12)

    def test_profile_discovery_run_omits_max_queries_by_default(self):
        args = operator_cli.build_parser().parse_args(
            [
                "profile-discovery",
                "run",
                "--profile-id",
                "11111111-1111-1111-1111-111111111111",
                "--searxng-url",
                "http://search.example.test",
            ]
        )

        self.assertIsNone(args.max_queries)

    def test_profile_discovery_run_rejects_non_positive_max_queries(self):
        for value in ("0", "-1"):
            with self.subTest(value=value):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    operator_cli.build_parser().parse_args(
                        [
                            "profile-discovery",
                            "run",
                            "--profile-id",
                            "11111111-1111-1111-1111-111111111111",
                            "--searxng-url",
                            "http://search.example.test",
                            "--max-queries",
                            value,
                        ]
                    )

    async def test_profile_discovery_run_passes_max_queries_to_service(self):
        await self._assert_dispatched_max_queries(expected=12, cli_args=["--max-queries", "12"])

    async def test_profile_discovery_run_omission_passes_none_to_service(self):
        await self._assert_dispatched_max_queries(expected=None, cli_args=[])

    async def _assert_dispatched_max_queries(self, *, expected, cli_args):
        args = operator_cli.build_parser().parse_args(
            [
                "profile-discovery",
                "run",
                "--profile-id",
                "11111111-1111-1111-1111-111111111111",
                "--searxng-url",
                "http://search.example.test",
                *cli_args,
            ]
        )
        config = SimpleNamespace(
            searxng_url=None,
            source_discovery_interval_seconds=3600,
            postgresql_url=MagicMock(return_value="postgresql://example"),
        )
        database = MagicMock()
        database.connect.return_value = _AsyncContext("connection")
        database.close = AsyncMock()
        profile = SimpleNamespace(
            id=args.profile_id,
            revision=1,
            is_active=True,
            confirmation_status=SimpleNamespace(value="confirmed"),
        )
        service = MagicMock()
        service.discover_profile = AsyncMock(return_value=SimpleNamespace())
        repository = MagicMock()
        repository.get = AsyncMock(return_value=profile)

        with (
            patch("freelancer_bot.operator_cli._database_config", return_value=config),
            patch("freelancer_bot.operator_cli.Database", return_value=database),
            patch("freelancer_bot.operator_cli.WebDiscoveryGovernor.from_config"),
            patch("freelancer_bot.operator_cli.ProfileDiscoveryService", return_value=service),
            patch("freelancer_bot.operator_cli.SearchProfileRepository", return_value=repository),
            patch("freelancer_bot.operator_cli._profile_execution_payload", return_value={}),
            patch("freelancer_bot.operator_cli._emit"),
        ):
            await operator_cli._profile_discovery_command(args)

        service.discover_profile.assert_awaited_once()
        self.assertEqual(
            service.discover_profile.await_args.kwargs["max_queries"],
            expected,
        )
        database.close.assert_awaited_once()

    def test_profile_execution_payload_exposes_bounded_plan_at_top_level(self):
        execution = self._execution(
            provider_observability={
                "queries_executable": 34,
                "queries_selected": 12,
                "queries_executed": 12,
                "query_limit": 12,
                "query_angle_counts": {
                    "executable": {
                        "direct": 16,
                        "buyer_habitat": 10,
                        "adjacent": 8,
                    },
                    "selected": {
                        "direct": 4,
                        "buyer_habitat": 4,
                        "adjacent": 4,
                    },
                },
            }
        )

        payload = operator_cli._profile_execution_payload(execution)

        self.assertEqual(payload["generated_query_count"], 36)
        self.assertEqual(payload["executable_query_count"], 34)
        self.assertEqual(payload["selected_query_count"], 12)
        self.assertEqual(payload["executed_query_count"], 12)
        self.assertEqual(payload["query_limit"], 12)
        self.assertEqual(payload["direct_query_count"], 16)
        self.assertEqual(payload["buyer_habitat_query_count"], 10)
        self.assertEqual(payload["adjacent_query_count"], 8)
        self.assertEqual(
            payload["selected_query_angle_counts"],
            {"direct": 4, "buyer_habitat": 4, "adjacent": 4},
        )
        self.assertEqual(
            payload["executable_query_angle_counts"],
            {"direct": 16, "buyer_habitat": 10, "adjacent": 8},
        )

    def test_profile_execution_payload_exposes_unbounded_plan_without_limit(self):
        execution = self._execution(
            provider_observability={
                "queries_executable": 34,
                "queries_selected": 34,
                "queries_executed": 20,
                "query_limit": None,
                "query_angle_counts": {
                    "selected": {
                        "direct": 16,
                        "buyer_habitat": 10,
                        "adjacent": 8,
                    },
                },
            }
        )

        payload = operator_cli._profile_execution_payload(execution)

        self.assertEqual(payload["executable_query_count"], 34)
        self.assertEqual(payload["selected_query_count"], 34)
        self.assertEqual(payload["executed_query_count"], 20)
        self.assertIsNone(payload["query_limit"])
        self.assertEqual(
            payload["selected_query_angle_counts"],
            {"direct": 16, "buyer_habitat": 10, "adjacent": 8},
        )

    def test_profile_execution_payload_tolerates_missing_observability(self):
        payload = operator_cli._profile_execution_payload(
            self._execution(provider_observability={})
        )

        self.assertIsNone(payload["executable_query_count"])
        self.assertIsNone(payload["selected_query_count"])
        self.assertIsNone(payload["executed_query_count"])
        self.assertIsNone(payload["query_limit"])
        self.assertEqual(payload["selected_query_angle_counts"], {})

    def _execution(self, *, provider_observability):
        now = datetime(2026, 9, 8, tzinfo=timezone.utc)
        intent = SimpleNamespace(
            id="intent-id",
            search_profile_id="profile-id",
            profile_revision=1,
            version="profile-discovery-intent.v1",
            roles=("Python developer",),
            services=("Telegram bots",),
            skills=("Telethon",),
            industries=("Telegram bots",),
            languages=("en", "ru"),
            geo_remote={"geographies": [], "work_modes": ["remote"]},
            likely_buyer_roles=("founder",),
            buyer_habitats=("startup founders",),
            literal_concepts=("Python developer",),
            adjacent_concepts=("Python agency",),
            generated_web_queries=("q",) * 36,
        )
        run = SimpleNamespace(
            id="run-id",
            provider="web_search",
            provider_kind="web",
            run_key="run-key",
            status=SimpleNamespace(value="completed"),
            result_count=1,
            materialized_count=1,
            failure_code=None,
            started_at=now,
            finished_at=now,
            created_at=now,
            request={},
        )
        return SimpleNamespace(
            profile_key="profile-id",
            intent=intent,
            execution=SimpleNamespace(run=run),
            generated_query_count=36,
            direct_query_count=16,
            buyer_habitat_query_count=10,
            adjacent_query_count=8,
            search_results_considered=0,
            telegram_like_candidates=0,
            unique_candidates=0,
            known_candidates=0,
            new_candidates=0,
            overlap_with_previous_profiles=0,
            candidate_priority_counts={},
            provider_observability=provider_observability,
            coverage=None,
        )


if __name__ == "__main__":
    unittest.main()
