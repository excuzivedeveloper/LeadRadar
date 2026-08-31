from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import unittest
import urllib.error
from uuid import UUID, uuid4

import sqlalchemy as sa

from freelancer_bot.config import RuntimeConfig
from freelancer_bot.ingestion_runtime import _configured_analyzer
from freelancer_bot.message_prefilter import (
    OPPORTUNITY_ANALYSIS_JOB_TYPE,
    RawMessagePrefilterProcessor,
)
from freelancer_bot.opportunity_analysis import (
    OPPORTUNITY_ANALYSIS_SCHEMA_VERSION,
    opportunity_analysis_cache_version,
)
from freelancer_bot.opportunity_one_shot import (
    OpportunityAnalysisOneShotError,
    run_opportunity_analysis_job_once,
)
from freelancer_bot.persistence.collector_accounts import CollectorAccountRepository
from freelancer_bot.persistence.database import Database
from freelancer_bot.persistence.jobs import DurableJobRepository, JobClaim
from freelancer_bot.persistence.message_prefilter import (
    MessagePrefilterRepository,
    OpportunityAnalysisCacheRepository,
)
from freelancer_bot.persistence.opportunities import CanonicalOpportunityRepository
from freelancer_bot.persistence.raw_messages import (
    RAW_MESSAGE_JOB_TYPE,
    RawMessageIngestor,
    RawMessageInput,
    RawMessageOrigin,
)
from freelancer_bot.persistence.schema import (
    ai_call_telemetry,
    durable_jobs,
    opportunities,
    opportunity_analysis_cache,
)
from freelancer_bot.persistence.source_repository import SourceRepository, SourceStatus
from postgres_support import TEST_DATABASE_URL, migrate_to_head, temporary_database


NOW = datetime.now(timezone.utc)
TRACE_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not configured")
class OpportunityAnalysisOneShotTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.database_context = temporary_database()
        self.database_url = self.database_context.__enter__()
        migrate_to_head(self.database_url)
        self.database = Database(self.database_url, pool_size=8, max_overflow=16)
        self.jobs = DurableJobRepository()
        self.sources = SourceRepository()
        self.accounts = CollectorAccountRepository()
        self.prefilters = MessagePrefilterRepository()
        self.cache = OpportunityAnalysisCacheRepository()
        self.opportunities = CanonicalOpportunityRepository()
        self.config = RuntimeConfig(
            app_environment="test",
            database_url=self.database_url,
            opportunity_analysis_provider="openrouter",
            opportunity_analysis_model="minimax/minimax-m3:free",
            openrouter_api_key="test-openrouter-key",
            opportunity_analysis_max_output_attempts=1,
            opportunity_analysis_fallback_enabled=False,
            worker_poll_interval_seconds=0.01,
            worker_lease_seconds=1,
            worker_heartbeat_seconds=0.1,
            worker_retry_delay_seconds=0,
            worker_shutdown_timeout_seconds=0.1,
            _env_file=None,
        )

    async def asyncSetUp(self):
        async with self.database.transaction() as connection:
            self.account = await self.accounts.ensure(
                connection,
                platform="telegram",
                external_account_id="91002",
                display_name="one-shot collector",
            )
            candidate = await self.sources.create_candidate(
                connection,
                platform="telegram",
                external_id="username:one_shot",
                access_type="public",
                display_name="one-shot source",
                handle="@one_shot",
                canonical_url="https://t.me/one_shot",
                provider="one_shot_fixture",
                lineage_key="one-shot:source",
            )
            self.source = await self.sources.transition(
                connection,
                candidate.id,
                SourceStatus.APPROVED,
                reason="one-shot fixture approved",
            )

    async def asyncTearDown(self):
        await self.database.close()
        self.database_context.__exit__(None, None, None)

    async def test_nonexistent_uuid_rejects_before_provider_request(self):
        requests = []

        with self._patched_urlopen(requests, _openrouter_response(_analysis_payload())):
            with self.assertRaisesRegex(OpportunityAnalysisOneShotError, "does not exist"):
                await run_opportunity_analysis_job_once(
                    self.config,
                    uuid4(),
                    database=self.database,
                    repository=self.jobs,
                )

        self.assertEqual(requests, [])

    async def test_wrong_job_type_rejects_before_provider_request(self):
        async with self.database.transaction() as connection:
            job_id = await self.jobs.enqueue(
                connection,
                job_type="matching.delivery.v1",
                idempotency_key="wrong-type",
            )
        requests = []

        with self._patched_urlopen(requests, _openrouter_response(_analysis_payload())):
            with self.assertRaisesRegex(OpportunityAnalysisOneShotError, "not opportunity"):
                await run_opportunity_analysis_job_once(
                    self.config,
                    job_id,
                    database=self.database,
                    repository=self.jobs,
                )

        self.assertEqual(requests, [])

    async def test_ineligible_states_reject_before_provider_request(self):
        states = {
            "completed": await self._analysis_job("completed-state", 100),
            "failed": await self._analysis_job("failed-state", 101),
            "running": await self._analysis_job("running-state", 102),
            "future": await self._analysis_job("future-state", 103),
            "exhausted": await self._analysis_job("exhausted-state", 104),
        }
        await self._complete(states["completed"])
        await self._fail_terminal(states["failed"])
        await self._claim_running(states["running"])
        await self._make_future(states["future"])
        await self._make_exhausted(states["exhausted"])
        requests = []

        with self._patched_urlopen(requests, _openrouter_response(_analysis_payload())):
            for name, job_id in states.items():
                with self.subTest(name=name):
                    with self.assertRaises(OpportunityAnalysisOneShotError):
                        await run_opportunity_analysis_job_once(
                            self.config,
                            job_id,
                            database=self.database,
                            repository=self.jobs,
                        )

        self.assertEqual(requests, [])

    async def test_one_shot_processes_selected_job_only_and_persists_analysis(self):
        selected = await self._analysis_job("selected", 200)
        untouched = await self._analysis_job("untouched", 201)
        requests = []

        with self._patched_urlopen(requests, _openrouter_response(_analysis_payload())):
            result = await run_opportunity_analysis_job_once(
                self.config,
                selected,
                database=self.database,
                repository=self.jobs,
            )

        self.assertTrue(result.processed)
        self.assertEqual(len(requests), 1)
        async with self.database.connect() as connection:
            selected_row = await self.jobs.get(connection, selected)
            untouched_row = await self.jobs.get(connection, untouched)
            telemetry = (
                await connection.execute(sa.select(ai_call_telemetry))
            ).mappings().one()
            cache_count = await connection.scalar(
                sa.select(sa.func.count()).select_from(opportunity_analysis_cache)
            )
            opportunity_count = await connection.scalar(
                sa.select(sa.func.count()).select_from(opportunities)
            )
        self.assertEqual(selected_row["state"], "completed")
        self.assertEqual(selected_row["attempt_count"], 1)
        self.assertEqual(untouched_row["state"], "queued")
        self.assertEqual(untouched_row["attempt_count"], 0)
        self.assertEqual(telemetry["provider"], "openrouter")
        self.assertEqual(telemetry["requested_model"], "minimax/minimax-m3:free")
        self.assertEqual(telemetry["status"], "succeeded")
        self.assertEqual(cache_count, 1)
        self.assertEqual(opportunity_count, 1)

    async def test_invalid_output_uses_one_request_and_retry_semantics(self):
        selected = await self._analysis_job("invalid-output", 300)
        untouched = await self._analysis_job("invalid-untouched", 301)
        requests = []

        with self._patched_urlopen(
            requests,
            {"model": "minimax/minimax-m3:free", "choices": [], "usage": _usage()},
        ):
            await run_opportunity_analysis_job_once(
                self.config,
                selected,
                database=self.database,
                repository=self.jobs,
            )

        self.assertEqual(len(requests), 1)
        async with self.database.connect() as connection:
            selected_row = await self.jobs.get(connection, selected)
            untouched_row = await self.jobs.get(connection, untouched)
            telemetry = (
                await connection.execute(sa.select(ai_call_telemetry))
            ).mappings().one()
        self.assertEqual(selected_row["state"], "queued")
        self.assertEqual(selected_row["attempt_count"], 1)
        self.assertEqual(selected_row["failure_code"], "OpportunityAnalysisOutputError")
        self.assertEqual(untouched_row["state"], "queued")
        self.assertEqual(untouched_row["attempt_count"], 0)
        self.assertEqual(telemetry["status"], "invalid_output")

    async def test_transport_failure_uses_one_request_and_retry_semantics(self):
        selected = await self._analysis_job("transport-failure", 400)
        untouched = await self._analysis_job("transport-untouched", 401)
        requests = []

        def fail_urlopen(request, timeout):
            requests.append((request, timeout))
            raise urllib.error.URLError("fixture network failure")

        with self._patch_urlopen(fail_urlopen):
            await run_opportunity_analysis_job_once(
                self.config,
                selected,
                database=self.database,
                repository=self.jobs,
            )

        self.assertEqual(len(requests), 1)
        async with self.database.connect() as connection:
            selected_row = await self.jobs.get(connection, selected)
            untouched_row = await self.jobs.get(connection, untouched)
            telemetry = (
                await connection.execute(sa.select(ai_call_telemetry))
            ).mappings().one()
        self.assertEqual(selected_row["state"], "queued")
        self.assertEqual(selected_row["attempt_count"], 1)
        self.assertEqual(selected_row["failure_code"], "OpportunityAnalysisError")
        self.assertEqual(untouched_row["state"], "queued")
        self.assertEqual(untouched_row["attempt_count"], 0)
        self.assertEqual(telemetry["status"], "request_failed")

    async def _analysis_job(self, key: str, external_message_id: int) -> UUID:
        result = await RawMessageIngestor(self.database, jobs=self.jobs).ingest(
            RawMessageInput(
                source_id=self.source.id,
                collector_account_id=self.account.id,
                external_message_id=external_message_id,
                message_date=NOW,
                observed_at=NOW,
                message_url=f"https://t.me/one_shot/{external_message_id}",
                content=f"Нужен Python разработчик для проекта {key}",
                transport_metadata={},
                ingestion_origin=RawMessageOrigin.LIVE,
                correlation_id=TRACE_ID,
            )
        )
        raw_claim = await self._claim(result.message.processing_job_id, RAW_MESSAGE_JOB_TYPE)
        analyzer = _configured_analyzer(self.database, self.config)
        self.assertIsNotNone(analyzer)
        prefilter = await RawMessagePrefilterProcessor(
            self.database,
            jobs=self.jobs,
            analyzer_version=opportunity_analysis_cache_version(analyzer),
            analysis_schema_version=analyzer.schema_version,
        ).process(raw_claim)
        async with self.database.transaction() as connection:
            await self.jobs.complete(connection, raw_claim)
        self.assertIsNotNone(prefilter.analysis_job_id)
        return prefilter.analysis_job_id

    async def _claim(self, job_id: UUID, job_type: str) -> JobClaim:
        async with self.database.transaction() as connection:
            claim = await self.jobs.claim_next(
                connection,
                worker_id="one-shot-test-prep",
                lease_duration=timedelta(seconds=1),
                job_types=(job_type,),
                job_ids=(job_id,),
            )
        self.assertIsNotNone(claim)
        return claim

    async def _complete(self, job_id: UUID) -> None:
        claim = await self._claim(job_id, OPPORTUNITY_ANALYSIS_JOB_TYPE)
        async with self.database.transaction() as connection:
            await self.jobs.complete(connection, claim)

    async def _fail_terminal(self, job_id: UUID) -> None:
        claim = await self._claim(job_id, OPPORTUNITY_ANALYSIS_JOB_TYPE)
        async with self.database.transaction() as connection:
            await self.jobs.fail(
                connection,
                claim,
                failure_code="FixtureTerminal",
                retry_delay=timedelta(seconds=0),
                retryable=False,
            )

    async def _claim_running(self, job_id: UUID) -> None:
        await self._claim(job_id, OPPORTUNITY_ANALYSIS_JOB_TYPE)

    async def _make_future(self, job_id: UUID) -> None:
        async with self.database.transaction() as connection:
            await connection.execute(
                sa.update(durable_jobs)
                .where(durable_jobs.c.id == job_id)
                .values(available_at=sa.func.now() + sa.text("INTERVAL '1 hour'"))
            )

    async def _make_exhausted(self, job_id: UUID) -> None:
        async with self.database.transaction() as connection:
            await connection.execute(
                sa.update(durable_jobs)
                .where(durable_jobs.c.id == job_id)
                .values(attempt_count=durable_jobs.c.max_attempts)
            )

    @contextmanager
    def _patched_urlopen(self, requests: list[object], response: dict[str, object]):
        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return _FakeResponse(response)

        with self._patch_urlopen(fake_urlopen):
            yield

    @contextmanager
    def _patch_urlopen(self, replacement):
        from unittest.mock import patch

        with patch("freelancer_bot.opportunity_analysis.urllib.request.urlopen", replacement):
            yield


def _openrouter_response(analysis: dict[str, object]) -> dict[str, object]:
    return {
        "model": "minimax/minimax-m3:free",
        "choices": [{"message": {"content": json.dumps(analysis)}}],
        "usage": _usage(),
    }


def _analysis_payload() -> dict[str, object]:
    return {
        "schema_version": OPPORTUNITY_ANALYSIS_SCHEMA_VERSION,
        "is_opportunity": True,
        "confidence": 0.91,
        "market_direction": "buyer_to_specialist",
        "intent_stage": "active",
        "opportunity_type": "project",
        "category": "software_development",
        "role_title": "Python developer",
        "skills": ["Python"],
        "task_summary": "Python project work",
        "budget": {
            "known": False,
            "min": None,
            "max": None,
            "currency": None,
            "period": None,
            "explicit": False,
        },
        "work": {
            "remote": None,
            "location": None,
            "full_time": None,
            "part_time": None,
        },
        "language": "ru",
        "contact": {
            "telegram": None,
            "email": None,
            "url": None,
        },
        "quality": {
            "actionability": 0.8,
            "commercial_plausibility": 0.8,
            "specificity": 0.7,
            "credibility": 0.7,
        },
        "red_flags": [],
    }


def _usage() -> dict[str, int]:
    return {"prompt_tokens": 41, "completion_tokens": 23, "total_tokens": 64}


if __name__ == "__main__":
    unittest.main()
