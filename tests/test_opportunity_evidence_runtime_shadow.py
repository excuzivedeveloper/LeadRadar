from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import io
import json
from types import SimpleNamespace
import unittest
from unittest import mock
from uuid import UUID, uuid4

import sqlalchemy as sa

from freelancer_bot.config import RuntimeConfig
from freelancer_bot.delivery import DeliveryScheduleReport
from freelancer_bot.match_decisions import MatchDecisionCode, MatchDecisionPolicy
from freelancer_bot.matching_delivery import (
    MATCHING_DELIVERY_JOB_TYPE,
    MatchingDeliveryJobProcessor,
    matching_job_idempotency_key,
)
from freelancer_bot.matching_service import CandidateMatchingService
from freelancer_bot.metrics import InMemoryMetrics, MetricNames
from freelancer_bot.observability import Redactor, configure_structured_logger
from freelancer_bot.opportunity_analysis import OPPORTUNITY_ANALYSIS_SCHEMA_VERSION
from freelancer_bot.opportunity_evidence import (
    EvidenceOrigin,
    EvidenceVerification,
    OPPORTUNITY_EVIDENCE_SHADOW_VERSION,
)
from freelancer_bot.persistence.database import Database
from freelancer_bot.persistence.matches import MatchTraceRepository
from freelancer_bot.persistence.opportunities import (
    CANONICAL_OPPORTUNITY_SCHEMA_VERSION,
    CanonicalOpportunityRepository,
)
from freelancer_bot.persistence.opportunity_evidence_shadow import (
    OPPORTUNITY_EVIDENCE_RAW_SOURCE_POLICY_VERSION,
    OPPORTUNITY_EVIDENCE_SHADOW_TRACE_SCHEMA_VERSION,
    OpportunityEvidenceShadowConflict,
    OpportunityEvidenceShadowDraft,
    OpportunityEvidenceShadowRecorder,
    OpportunityEvidenceShadowRepository,
    build_opportunity_evidence_shadow_draft,
    select_opportunity_evidence_raw_message_id,
)
from freelancer_bot.persistence.raw_messages import RawMessageRepository
from freelancer_bot.persistence.schema import (
    collector_accounts,
    durable_jobs,
    opportunity_evidence_shadow_traces,
    opportunities,
    opportunity_source_messages,
    personalized_deliveries,
    raw_messages,
    search_profiles,
    sources,
    users,
)
from freelancer_bot.persistence.search_profiles import SearchProfileRepository
from freelancer_bot.profile_confirmation import ProfileConfirmationService
from freelancer_bot.search_profiles import (
    SEARCH_PROFILE_PREFERENCES_SCHEMA_VERSION,
    parse_search_profile,
)
from postgres_support import TEST_DATABASE_URL, migrate_to_head, temporary_database


NOW = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)


class MatchingDeliveryShadowOrchestrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_shadow_success_does_not_change_matching_or_delivery_result(self):
        outcome = _fake_matching_outcome()
        matching = _FakeMatching(outcome)
        delivery = _FakeDelivery()
        recorder = _FakeShadowRecorder()
        processor = MatchingDeliveryJobProcessor(
            _FakeDatabase(),
            RuntimeConfig(_env_file=None),
            matching=matching,
            deliveries=delivery,
            evidence_shadow_recorder=recorder,
            jobs=_FakeJobs(NOW),
        )

        result = await processor.process(_claim(outcome.opportunity_id))

        self.assertIs(result.matching, outcome)
        self.assertIs(result.delivery, delivery.report)
        self.assertEqual(matching.calls, 1)
        self.assertEqual(delivery.run_ids, [outcome.persistence.run.id])
        self.assertEqual(recorder.traces, [outcome.persistence.traces])

    async def test_shadow_failure_is_fail_open_after_delivery_scheduling(self):
        outcome = _fake_matching_outcome()
        metrics = InMemoryMetrics()
        log_output = io.StringIO()
        logger = configure_structured_logger(
            "test.runtime-shadow.fail-open",
            redactor=Redactor(),
            stream=log_output,
        )
        processor = MatchingDeliveryJobProcessor(
            _FakeDatabase(),
            RuntimeConfig(_env_file=None),
            matching=_FakeMatching(outcome),
            deliveries=_FakeDelivery(),
            evidence_shadow_recorder=_FailingShadowRecorder(),
            jobs=_FakeJobs(NOW),
            metrics=metrics,
            logger=logger,
        )

        result = await processor.process(_claim(outcome.opportunity_id))

        self.assertIs(result.matching, outcome)
        self.assertEqual(result.delivery.created_count, 1)
        self.assertEqual(
            metrics.counter(
                MetricNames.MATCHING_EVIDENCE_SHADOW_FAILURES,
                tags={"error_type": "RuntimeError"},
            ),
            1,
        )
        logs = log_output.getvalue()
        self.assertIn("matching.opportunity_evidence_shadow_failed", logs)
        self.assertNotIn("Нужен ИИ-менеджер", logs)


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not configured")
class OpportunityEvidenceRuntimeShadowPostgresTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.database_context = temporary_database()
        self.database_url = self.database_context.__enter__()
        migrate_to_head(self.database_url)
        self.database = Database(self.database_url, pool_size=6, max_overflow=8)
        self.metrics = InMemoryMetrics()
        self.log_output = io.StringIO()
        self.logger = configure_structured_logger(
            f"test.runtime-shadow.{id(self)}",
            redactor=Redactor(),
            stream=self.log_output,
        )

    async def asyncTearDown(self):
        await self.database.close()
        self.database_context.__exit__(None, None, None)

    async def test_repository_create_reuse_and_conflict(self):
        _, trace = await self._match_trace(
            raw_text="Нужен FastAPI разработчик",
            skills=("FastAPI",),
            profile_skill="FastAPI",
        )
        draft = await self._draft_for_trace(trace)
        repository = OpportunityEvidenceShadowRepository()

        async with self.database.transaction() as connection:
            first = await repository.persist(connection, draft)
            reused = await repository.persist(connection, draft)

        self.assertTrue(first.created)
        self.assertFalse(reused.created)
        self.assertEqual(first.record.id, reused.record.id)
        async with self.database.connect() as connection:
            rows = await repository.list_for_match_run(connection, trace.run_id)
        self.assertEqual(len(rows), 1)

        changed = replace(
            draft,
            payload_sha256="0" * 64,
            shadow_payload={**draft.shadow_payload, "score": "0.9999"},
        )
        with self.assertRaises(OpportunityEvidenceShadowConflict):
            async with self.database.transaction() as connection:
                await repository.persist(connection, changed)

    async def test_recorder_runtime_path_preserves_raw_grounding(self):
        _, hallucinated = await self._match_trace(
            raw_text="Нужен ИИ-менеджер для заявок",
            skills=("FastAPI",),
            profile_skill="FastAPI",
        )
        _, explicit = await self._match_trace(
            raw_text="Нужен FastAPI разработчик",
            skills=("FastAPI",),
            profile_skill="FastAPI",
        )
        recorder = OpportunityEvidenceShadowRecorder(
            self.database,
            metrics=self.metrics,
            logger=self.logger,
        )

        report = await recorder.record_match_run((hallucinated, explicit))

        self.assertEqual(report.failed, 0)
        async with self.database.connect() as connection:
            rows = await OpportunityEvidenceShadowRepository().list_for_match_run(
                connection,
                explicit.run_id,
            )
            hallucinated_row = await OpportunityEvidenceShadowRepository().get(
                connection,
                match_trace_id=hallucinated.id,
            )
        self.assertEqual(len(rows), 1)
        self.assertIsNotNone(hallucinated_row)
        hallucinated_evidence = _evidence_by_identity(
            hallucinated_row.shadow_payload["evidence"]
        )
        explicit_evidence = _evidence_by_identity(rows[0].shadow_payload["evidence"])

        self.assertNotIn(("technology", "fastapi"), hallucinated_evidence)
        fastapi = explicit_evidence[("technology", "fastapi")]
        self.assertEqual(fastapi["origin"], EvidenceOrigin.RAW_EXPLICIT.value)
        self.assertEqual(
            fastapi["verification"],
            EvidenceVerification.RAW_SPAN_VERIFIED.value,
        )

    async def test_recorder_reuses_retry_and_sanitizes_payload(self):
        raw_text = "Нужен FastAPI разработчик. Пишите @secret_user +79991234567."
        _, trace = await self._match_trace(
            raw_text=raw_text,
            skills=("FastAPI",),
            profile_skill="FastAPI",
            semantic_text="FastAPI profile semantic secret@example.com",
        )
        recorder = OpportunityEvidenceShadowRecorder(self.database)

        first = await recorder.record_match_run((trace,))
        second = await recorder.record_match_run((trace,))

        self.assertEqual((first.created, first.reused), (1, 0))
        self.assertEqual((second.created, second.reused), (0, 1))
        async with self.database.connect() as connection:
            rows = await OpportunityEvidenceShadowRepository().list_for_match_run(
                connection,
                trace.run_id,
            )
            row_count = await connection.scalar(
                sa.select(sa.func.count()).select_from(
                    opportunity_evidence_shadow_traces
                )
            )
        self.assertEqual(row_count, 1)
        serialized = json.dumps(rows[0].shadow_payload, ensure_ascii=False)
        self.assertNotIn(raw_text, serialized)
        self.assertNotIn("@secret_user", serialized)
        self.assertNotIn("+79991234567", serialized)
        self.assertNotIn("secret@example.com", serialized)
        self.assertEqual(
            rows[0].raw_content_sha256,
            sha256(raw_text.encode("utf-8")).hexdigest(),
        )

    async def test_profile_revision_guard_fails_open_per_trace(self):
        profile_id, trace = await self._match_trace(
            raw_text="Нужен FastAPI разработчик",
            skills=("FastAPI",),
            profile_skill="FastAPI",
        )
        async with self.database.transaction() as connection:
            await connection.execute(
                search_profiles.update()
                .where(search_profiles.c.id == profile_id)
                .values(revision=search_profiles.c.revision + 1)
            )
        recorder = OpportunityEvidenceShadowRecorder(
            self.database,
            metrics=self.metrics,
            logger=self.logger,
        )

        report = await recorder.record_match_run((trace,))

        self.assertEqual(report.failed, 1)
        async with self.database.connect() as connection:
            rows = await OpportunityEvidenceShadowRepository().list_for_match_run(
                connection,
                trace.run_id,
            )
        self.assertEqual(rows, ())
        self.assertIn(
            "matching.opportunity_evidence_shadow_failed",
            self.log_output.getvalue(),
        )

    async def test_raw_source_selection_prefers_then_falls_back_deterministically(self):
        old_raw = uuid4()
        new_raw = uuid4()
        opportunity = SimpleNamespace(
            preferred_source=SimpleNamespace(raw_message_id=new_raw),
            source_observations=(
                SimpleNamespace(raw_message_id=old_raw, message_date=NOW),
                SimpleNamespace(raw_message_id=new_raw, message_date=NOW),
            ),
        )
        self.assertEqual(select_opportunity_evidence_raw_message_id(opportunity), new_raw)

        fallback = SimpleNamespace(
            preferred_source=None,
            source_observations=(
                SimpleNamespace(raw_message_id=new_raw, message_date=NOW),
                SimpleNamespace(
                    raw_message_id=old_raw,
                    message_date=NOW - timedelta(minutes=1),
                ),
            ),
        )
        self.assertEqual(select_opportunity_evidence_raw_message_id(fallback), old_raw)

    async def test_current_shadow_disagreement_is_persisted_without_convergence(self):
        _, trace = await self._match_trace(
            raw_text="Нужен FastAPI разработчик",
            skills=("FastAPI",),
            profile_skill="FastAPI",
        )
        disagreed = replace(
            trace,
            trace=replace(
                trace.trace,
                decision_code=MatchDecisionCode.HARD_REJECTED,
                eligible=False,
                rank=None,
                final_rank_score=None,
            ),
        )
        recorder = OpportunityEvidenceShadowRecorder(self.database)

        report = await recorder.record_match_run((disagreed,))

        self.assertEqual(report.created, 1)
        async with self.database.connect() as connection:
            row = await OpportunityEvidenceShadowRepository().get(
                connection,
                match_trace_id=trace.id,
            )
        self.assertEqual(row.current_decision_code, "hard_rejected")
        self.assertFalse(row.current_eligible)
        self.assertEqual(row.shadow_decision, "strong_eligible")

    async def test_shadow_write_uses_independent_transaction_boundary(self):
        _, trace = await self._match_trace(
            raw_text="Нужен FastAPI разработчик",
            skills=("FastAPI",),
            profile_skill="FastAPI",
        )
        recorder = OpportunityEvidenceShadowRecorder(
            self.database,
            shadows=_AlwaysFailingShadowRepository(),
        )

        report = await recorder.record_match_run((trace,))

        self.assertEqual(report.failed, 1)
        async with self.database.connect() as connection:
            live_trace = await MatchTraceRepository().get(connection, trace.id)
            deliveries = await connection.scalar(
                sa.select(sa.func.count()).select_from(personalized_deliveries)
            )
        self.assertIsNotNone(live_trace)
        self.assertEqual(deliveries, 0)

    async def _match_trace(
        self,
        *,
        raw_text: str,
        skills: tuple[str, ...],
        profile_skill: str,
        semantic_text: str | None = None,
    ):
        profile = await self._active_profile(
            skill=profile_skill,
            semantic_text=semantic_text or profile_skill,
        )
        opportunity_id = await self._opportunity(raw_text=raw_text, skills=skills)
        generated = await CandidateMatchingService(self.database).generate_matches(
            (opportunity_id,),
            evaluated_at=NOW,
            decision_policy=MatchDecisionPolicy(
                minimum_relevance_score=Decimal("0.0000"),
                minimum_rank_score=Decimal("0.0000"),
            ),
        )
        trace = next(
            record
            for record in generated.persistence.traces
            if record.trace.search_profile_id == profile.id
        )
        return profile.id, trace

    async def _active_profile(
        self,
        *,
        skill: str,
        semantic_text: str,
    ):
        profiles = ProfileConfirmationService(self.database)
        external_user_id = f"runtime-shadow-{uuid4().hex}"
        draft = await profiles.create_manual_draft(
            platform="telegram",
            external_user_id=external_user_id,
            semantic_text=semantic_text,
            roles=(f"{skill} developer",),
            skills=(skill,),
            categories=("backend",),
        )
        confirmed = await profiles.confirm(
            platform="telegram",
            external_user_id=external_user_id,
            profile_id=draft.profile.id,
            expected_revision=draft.profile.revision,
        )
        activated = await profiles.activate(
            platform="telegram",
            external_user_id=external_user_id,
            profile_id=confirmed.profile.id,
            expected_revision=confirmed.profile.revision,
            start_trial=False,
        )
        return activated.profile.profile

    async def _opportunity(self, *, raw_text: str, skills: tuple[str, ...]) -> UUID:
        opportunity_id = uuid4()
        raw_message_id = uuid4()
        raw_job_id = uuid4()
        source_key = uuid4().hex
        async with self.database.transaction() as connection:
            collector_id = await connection.scalar(
                collector_accounts.insert()
                .values(
                    platform="telegram",
                    external_account_id=f"runtime-shadow:{source_key}",
                    display_name="Runtime shadow collector",
                )
                .returning(collector_accounts.c.id)
            )
            source_id = await connection.scalar(
                sources.insert()
                .values(
                    platform="telegram",
                    external_id=f"username:runtime_shadow_{source_key}",
                    access_type="public",
                    lifecycle_status="approved",
                    display_name="Runtime shadow source",
                    handle=f"@runtime_shadow_{source_key}",
                    canonical_url=f"https://t.me/runtime_shadow_{source_key}",
                )
                .returning(sources.c.id)
            )
            await connection.execute(
                durable_jobs.insert().values(
                    id=raw_job_id,
                    job_type="telegram.raw_message.v1",
                    idempotency_key=sha256(
                        f"runtime-shadow:{raw_message_id}".encode("utf-8")
                    ).hexdigest(),
                    correlation_id=opportunity_id,
                )
            )
            await connection.execute(
                raw_messages.insert().values(
                    id=raw_message_id,
                    source_id=source_id,
                    collector_account_id=collector_id,
                    processing_job_id=raw_job_id,
                    schema_version="telegram.raw_message.v1",
                    platform="telegram",
                    external_source_id=f"username:runtime_shadow_{source_key}",
                    external_message_id=42,
                    message_date=NOW - timedelta(minutes=5),
                    observed_at=NOW - timedelta(minutes=5),
                    message_url=f"https://t.me/runtime_shadow_{source_key}/42",
                    content=raw_text,
                    transport_metadata={},
                    ingestion_origin="live",
                    correlation_id=opportunity_id,
                )
            )
            await connection.execute(
                opportunities.insert().values(
                    id=opportunity_id,
                    schema_version=CANONICAL_OPPORTUNITY_SCHEMA_VERSION,
                    canonical_title=skills[0],
                    task_summary=raw_text,
                    market_direction="buyer_to_specialist",
                    intent_stage="active",
                    opportunity_type="project",
                    category="backend",
                    role_title=f"{skills[0]} developer",
                    skills=list(skills),
                    budget_known=False,
                    budget_explicit=False,
                    work_remote=True,
                    analysis_confidence=Decimal("0.9000"),
                    quality_actionability=Decimal("0.8000"),
                    quality_commercial_plausibility=Decimal("0.8000"),
                    quality_specificity=Decimal("0.8000"),
                    quality_credibility=Decimal("0.8000"),
                    red_flags=[],
                    first_seen_at=NOW - timedelta(minutes=5),
                    last_seen_at=NOW - timedelta(minutes=5),
                    lifecycle_status="active",
                    lifecycle_changed_at=NOW - timedelta(minutes=5),
                    preferred_raw_message_id=raw_message_id,
                    preferred_source_policy_version="canonical-source.v1",
                )
            )
            await connection.execute(
                opportunity_source_messages.insert().values(
                    raw_message_id=raw_message_id,
                    opportunity_id=opportunity_id,
                )
            )
        return opportunity_id

    async def _draft_for_trace(self, trace):
        async with self.database.connect() as connection:
            opportunity = await CanonicalOpportunityRepository().get(
                connection,
                trace.trace.opportunity_id,
            )
            raw_id = select_opportunity_evidence_raw_message_id(opportunity)
            raw = await RawMessageRepository().get_by_id(connection, raw_id)
            profile = await SearchProfileRepository().get(
                connection,
                trace.trace.search_profile_id,
            )
        from freelancer_bot.opportunity_evidence import (
            build_opportunity_analysis_v2,
            evidence_aware_shadow_trace,
        )

        analysis = build_opportunity_analysis_v2(
            opportunity.analysis,
            raw_message_text=raw.content,
        )
        shadow = evidence_aware_shadow_trace(analysis, profile)
        return build_opportunity_evidence_shadow_draft(
            trace,
            raw=raw,
            shadow=shadow,
            analysis=analysis,
            profile=profile,
        )


def _evidence_by_identity(items):
    return {(item["dimension"], item["concept_id"]): item for item in items}


def _fake_matching_outcome():
    opportunity_id = uuid4()
    trace = SimpleNamespace(
        opportunity_id=opportunity_id,
        search_profile_id=uuid4(),
        profile_revision=1,
        decision_code=MatchDecisionCode.ELIGIBLE,
        eligible=True,
    )
    record = SimpleNamespace(id=uuid4(), run_id=uuid4(), trace=trace)
    run = SimpleNamespace(id=record.run_id)
    report = SimpleNamespace(
        eligible_match_count=1,
        user_specific_llm_calls=0,
        opportunity_analyzer_calls=0,
    )
    return SimpleNamespace(
        opportunity_id=opportunity_id,
        persistence=SimpleNamespace(run=run, traces=(record,), created=True),
        report=report,
    )


def _claim(opportunity_id: UUID):
    return SimpleNamespace(
        id=uuid4(),
        job_type=MATCHING_DELIVERY_JOB_TYPE,
        idempotency_key=matching_job_idempotency_key(opportunity_id),
    )


class _FakeDatabase:
    def connect(self):
        return _FakeConnect()


class _FakeConnect:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, traceback):
        return None


class _FakeJobs:
    def __init__(self, created_at: datetime) -> None:
        self.created_at = created_at

    async def get(self, connection, job_id):
        return {"id": job_id, "created_at": self.created_at}


class _FakeMatching:
    def __init__(self, outcome) -> None:
        self.outcome = outcome
        self.calls = 0

    async def generate_matches(self, opportunity_ids, **kwargs):
        self.calls += 1
        self.opportunity_ids = opportunity_ids
        self.kwargs = kwargs
        return self.outcome


class _FakeDelivery:
    def __init__(self) -> None:
        self.report = DeliveryScheduleReport(
            run_id=uuid4(),
            deliveries=(SimpleNamespace(created=True),),
            failures=(),
        )
        self.run_ids = []

    async def schedule_run(self, run_id, **kwargs):
        self.run_ids.append(run_id)
        self.kwargs = kwargs
        return self.report


class _FakeShadowRecorder:
    def __init__(self) -> None:
        self.traces = []

    async def record_match_run(self, traces):
        self.traces.append(traces)
        return SimpleNamespace(attempted=len(traces), created=len(traces), reused=0, failed=0)


class _FailingShadowRecorder:
    async def record_match_run(self, traces):
        raise RuntimeError("shadow failure")


class _AlwaysFailingShadowRepository:
    async def persist(self, connection, draft: OpportunityEvidenceShadowDraft):
        raise OpportunityEvidenceShadowConflict("forced shadow conflict")


if __name__ == "__main__":
    unittest.main()
