import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from freelancer_bot.app import cli, run_app
from freelancer_bot.config import RuntimeMode
from freelancer_bot.filters import FilterConfig
from freelancer_bot.replies import ReplyDraft
from freelancer_bot.sources import Source


class CliModeTest(unittest.TestCase):
    def test_default_cli_prints_help_without_starting_runtime(self):
        with (
            patch("sys.argv", ["freelancer_bot"]),
            patch("freelancer_bot.app.run_app", new_callable=AsyncMock) as run,
            redirect_stdout(io.StringIO()) as output,
        ):
            cli()

        run.assert_not_awaited()
        self.assertIn("--run", output.getvalue())

    def test_bot_only_is_explicit_and_uses_bot_only_mode(self):
        with (
            patch("sys.argv", ["freelancer_bot", "--bot-only"]),
            patch("freelancer_bot.app.run_app", new_callable=AsyncMock) as run,
        ):
            cli()

        run.assert_awaited_once_with(mode=RuntimeMode.BOT_ONLY)

    def test_run_is_explicit_and_uses_full_runtime_mode(self):
        with (
            patch("sys.argv", ["freelancer_bot", "--run"]),
            patch("freelancer_bot.app.run_app", new_callable=AsyncMock) as run,
        ):
            cli()

        run.assert_awaited_once_with(mode=RuntimeMode.RUN)

    def test_check_config_loads_config_without_runtime_credentials(self):
        config = SimpleNamespace(
            sources_path=Path("config/sources.json"),
            filters_path=Path("config/filters.json"),
        )
        source = Source("@test_source", "Test", "Fixture")
        filters = FilterConfig(5, {"telegram": 5}, ("smm",))

        with (
            patch("sys.argv", ["freelancer_bot", "--check-config"]),
            patch("freelancer_bot.app.RuntimeConfig.from_env", return_value=config) as from_env,
            patch("freelancer_bot.app.load_sources", return_value=[source]),
            patch("freelancer_bot.app.load_filter_config", return_value=filters),
            redirect_stdout(io.StringIO()),
        ):
            cli()

        from_env.assert_called_once_with(mode=RuntimeMode.CHECK_CONFIG)

    def test_check_filter_uses_check_filter_mode(self):
        config = SimpleNamespace(filters_path=Path("config/filters.json"))
        filters = FilterConfig(5, {"telegram": 5}, ())

        with (
            patch("sys.argv", ["freelancer_bot", "--check-filter", "telegram"]),
            patch("freelancer_bot.app.RuntimeConfig.from_env", return_value=config) as from_env,
            patch("freelancer_bot.app.load_filter_config", return_value=filters),
            redirect_stdout(io.StringIO()),
        ):
            cli()

        from_env.assert_called_once_with(mode=RuntimeMode.CHECK_FILTER)

    def test_check_sources_uses_user_only_mode(self):
        config = SimpleNamespace()
        source_check = AsyncMock()

        with (
            patch("sys.argv", ["freelancer_bot", "--check-sources"]),
            patch("freelancer_bot.app.RuntimeConfig.from_env", return_value=config) as from_env,
            patch("freelancer_bot.app.check_sources", source_check),
        ):
            cli()

        from_env.assert_called_once_with(mode=RuntimeMode.CHECK_SOURCES)
        source_check.assert_awaited_once_with(config)

    def test_opportunity_analysis_job_id_uses_one_shot_mode(self):
        config = SimpleNamespace()
        runner = AsyncMock()
        job_id = "11111111-1111-1111-1111-111111111111"

        with (
            patch(
                "sys.argv",
                ["freelancer_bot", "--opportunity-analysis-job-id", job_id],
            ),
            patch("freelancer_bot.app.RuntimeConfig.from_env", return_value=config) as from_env,
            patch("freelancer_bot.app.run_opportunity_analysis_job_once", runner),
            patch("freelancer_bot.app.TelegramClient") as telegram_client,
            patch("freelancer_bot.app.LeadBot") as lead_bot,
        ):
            cli()

        from_env.assert_called_once_with(mode=RuntimeMode.OPPORTUNITY_ANALYSIS_JOB)
        runner.assert_awaited_once_with(config, UUID(job_id))
        telegram_client.assert_not_called()
        lead_bot.assert_not_called()

    def test_opportunity_analysis_job_id_rejects_malformed_uuid_before_config(self):
        runner = AsyncMock()

        with (
            patch(
                "sys.argv",
                ["freelancer_bot", "--opportunity-analysis-job-id", "not-a-uuid"],
            ),
            patch("freelancer_bot.app.RuntimeConfig.from_env") as from_env,
            patch("freelancer_bot.app.run_opportunity_analysis_job_once", runner),
            self.assertRaises(SystemExit),
        ):
            cli()

        from_env.assert_not_called()
        runner.assert_not_awaited()

    def test_opportunity_analysis_job_id_expected_failure_exits_nonzero(self):
        from freelancer_bot.opportunity_one_shot import OpportunityAnalysisOneShotError

        runner = AsyncMock(
            side_effect=OpportunityAnalysisOneShotError(
                "Selected opportunity analysis job scheduled retry",
                status="retry_queued",
                job_state="queued",
                failure_code="OpportunityAnalysisOutputError",
            )
        )
        job_id = "11111111-1111-1111-1111-111111111111"

        with (
            patch(
                "sys.argv",
                ["freelancer_bot", "--opportunity-analysis-job-id", job_id],
            ),
            patch("freelancer_bot.app.RuntimeConfig.from_env", return_value=SimpleNamespace()),
            patch("freelancer_bot.app.run_opportunity_analysis_job_once", runner),
            redirect_stderr(io.StringIO()) as error_output,
            self.assertRaises(SystemExit) as raised,
        ):
            cli()

        self.assertEqual(raised.exception.code, 1)
        self.assertIn("status=retry_queued", error_output.getvalue())
        self.assertIn("state=queued", error_output.getvalue())
        self.assertIn("failure_code=OpportunityAnalysisOutputError", error_output.getvalue())

    def test_opportunity_analysis_job_id_conflict_with_check_sources_rejects_before_side_effects(self):
        self._assert_one_shot_conflict_rejected("--check-sources")

    def test_opportunity_analysis_job_id_conflict_with_run_rejects_before_side_effects(self):
        self._assert_one_shot_conflict_rejected("--run")

    def test_opportunity_analysis_job_id_conflict_with_bot_only_rejects_before_side_effects(self):
        self._assert_one_shot_conflict_rejected("--bot-only")

    def test_opportunity_analysis_job_id_conflict_with_collector_only_rejects_before_side_effects(self):
        self._assert_one_shot_conflict_rejected("--collector-only")

    def test_opportunity_analysis_job_id_conflict_with_check_config_rejects_before_side_effects(self):
        self._assert_one_shot_conflict_rejected("--check-config")

    def test_opportunity_analysis_job_id_conflict_with_check_filter_rejects_before_side_effects(self):
        self._assert_one_shot_conflict_rejected("--check-filter", "telegram")

    def test_opportunity_analysis_job_id_conflict_with_draft_text_rejects_before_side_effects(self):
        self._assert_one_shot_conflict_rejected("--draft-text", "Нужен telegram бот")

    def _assert_one_shot_conflict_rejected(self, *extra_args: str):
        runner = AsyncMock()
        job_id = "11111111-1111-1111-1111-111111111111"

        with (
            patch(
                "sys.argv",
                ["freelancer_bot", "--opportunity-analysis-job-id", job_id, *extra_args],
            ),
            patch("freelancer_bot.app.RuntimeConfig.from_env") as from_env,
            patch("freelancer_bot.app.run_opportunity_analysis_job_once", runner),
            patch("freelancer_bot.app.check_sources", new_callable=AsyncMock) as source_check,
            patch("freelancer_bot.app.run_app", new_callable=AsyncMock) as run,
            patch("freelancer_bot.app.run_collector_only", new_callable=AsyncMock) as collector,
            patch("freelancer_bot.app.TelegramClient") as telegram_client,
            redirect_stderr(io.StringIO()) as error_output,
            self.assertRaises(SystemExit),
        ):
            cli()

        self.assertIn("conflicting action modes", error_output.getvalue())
        from_env.assert_not_called()
        runner.assert_not_awaited()
        source_check.assert_not_awaited()
        run.assert_not_awaited()
        collector.assert_not_awaited()
        telegram_client.assert_not_called()

    def test_draft_text_uses_ai_only_mode(self):
        config = SimpleNamespace(
            freelancer_profile_path=Path("profile.json"),
            filters_path=Path("filters.json"),
        )
        filters = FilterConfig(5, {"telegram": 5}, ())
        provider = MagicMock()
        provider.generate.return_value = ReplyDraft(
            fit_summary="Подходит",
            fit_score=80,
            risks=(),
            questions_to_client=(),
            proposal_draft="Могу помочь.",
            short_reply="Могу помочь.",
        )

        with (
            patch("sys.argv", ["freelancer_bot", "--draft-text", "Нужен telegram бот"]),
            patch("freelancer_bot.app.RuntimeConfig.from_env", return_value=config) as from_env,
            patch("freelancer_bot.app.load_freelancer_profile", return_value={}),
            patch("freelancer_bot.app.load_filter_config", return_value=filters),
            patch("freelancer_bot.app._build_reply_draft_provider", return_value=provider),
            redirect_stdout(io.StringIO()),
        ):
            cli()

        from_env.assert_called_once_with(mode=RuntimeMode.DRAFT_TEXT)
        provider.generate.assert_called_once()


class RunAppModeTest(unittest.IsolatedAsyncioTestCase):
    async def test_normal_run_uses_full_runtime_mode(self):
        config = SimpleNamespace(log_level="INFO")
        application = MagicMock()
        application.run = AsyncMock()
        application.shutdown = AsyncMock()

        with (
            patch("freelancer_bot.app.RuntimeConfig.from_env", return_value=config) as from_env,
            patch("freelancer_bot.app.Redactor.from_config"),
            patch("freelancer_bot.app.configure_structured_logger"),
            patch("freelancer_bot.app.LeadBot", return_value=application),
        ):
            await run_app()

        from_env.assert_called_once_with(mode=RuntimeMode.RUN)
        application.run.assert_awaited_once()
        application.shutdown.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
