import io
import sys
import unittest
from contextlib import redirect_stderr
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


if __name__ == "__main__":
    unittest.main()
