from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from uuid import UUID

from .config import RuntimeConfig
from .delivery import DeliveryScheduleReport, PersonalizedDeliveryService
from .match_decisions import match_decision_policy_from_config
from .matching_service import CandidateMatchingService, MatchGenerationOutcome
from .metrics import MetricNames, MetricsSink, NoOpMetrics
from .observability import log_event
from .persistence.database import Database
from .persistence.jobs import DurableJobRepository, JobClaim
from .persistence.opportunity_evidence_shadow import (
    OpportunityEvidenceShadowRecorder,
)


MATCHING_DELIVERY_JOB_TYPE = "opportunity.matching_delivery.v1"
MATCHING_DELIVERY_MAX_ATTEMPTS = 5
MATCHING_JOB_KEY_PREFIX = "opportunity:"


@dataclass(frozen=True)
class MatchingDeliveryOutcome:
    opportunity_id: UUID
    matching: MatchGenerationOutcome
    delivery: DeliveryScheduleReport


def matching_job_idempotency_key(opportunity_id: UUID) -> str:
    return f"{MATCHING_JOB_KEY_PREFIX}{opportunity_id}"


def opportunity_id_from_matching_job_key(value: str) -> UUID:
    if not value.startswith(MATCHING_JOB_KEY_PREFIX):
        raise ValueError("matching job idempotency key has an unsupported prefix")
    try:
        return UUID(value.removeprefix(MATCHING_JOB_KEY_PREFIX))
    except ValueError:
        raise ValueError("matching job idempotency key has an invalid Opportunity id") from None


async def enqueue_matching_delivery(
    connection,
    *,
    jobs: DurableJobRepository,
    opportunity_id: UUID,
) -> UUID:
    """Enqueue the live fan-out once, in the Opportunity write transaction."""

    return await jobs.enqueue(
        connection,
        job_type=MATCHING_DELIVERY_JOB_TYPE,
        idempotency_key=matching_job_idempotency_key(opportunity_id),
        max_attempts=MATCHING_DELIVERY_MAX_ATTEMPTS,
        correlation_id=opportunity_id,
    )


class MatchingDeliveryJobProcessor:
    """Run the existing batch matcher and schedule its eligible deliveries."""

    def __init__(
        self,
        database: Database,
        config: RuntimeConfig,
        *,
        matching: CandidateMatchingService | None = None,
        deliveries: PersonalizedDeliveryService | None = None,
        evidence_shadow_recorder: OpportunityEvidenceShadowRecorder | None = None,
        jobs: DurableJobRepository | None = None,
        metrics: MetricsSink | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._database = database
        self._config = config
        self._metrics = metrics or NoOpMetrics()
        self._jobs = jobs or DurableJobRepository()
        self._matching = matching or CandidateMatchingService(
            database,
            metrics=self._metrics,
            logger=logger,
        )
        self._deliveries = deliveries or PersonalizedDeliveryService(
            database,
            metrics=self._metrics,
            logger=logger,
        )
        self._logger = logger or logging.getLogger(__name__)
        self._evidence_shadow_recorder = (
            evidence_shadow_recorder
            or OpportunityEvidenceShadowRecorder(
                database,
                metrics=self._metrics,
                logger=self._logger,
            )
        )

    async def __call__(self, claim: JobClaim) -> MatchingDeliveryOutcome:
        return await self.process(claim)

    async def process(self, claim: JobClaim) -> MatchingDeliveryOutcome:
        if claim.job_type != MATCHING_DELIVERY_JOB_TYPE:
            raise ValueError("matching processor received an unsupported job type")
        expected_key = matching_job_idempotency_key(
            opportunity_id_from_matching_job_key(claim.idempotency_key)
        )
        if claim.idempotency_key != expected_key:
            raise ValueError("matching job idempotency key is not canonical")
        opportunity_id = opportunity_id_from_matching_job_key(claim.idempotency_key)

        # The durable job's created_at is immutable. Reusing it on every retry
        # keeps the evaluation bucket stable across crashes and restarts.
        async with self._database.connect() as connection:
            job = await self._jobs.get(connection, claim.id)
        if job is None:
            raise LookupError(f"matching job {claim.id} does not exist")
        evaluated_at = _aware(job["created_at"])
        generated = await self._matching.generate_matches(
            (opportunity_id,),
            evaluated_at=evaluated_at,
            decision_policy=match_decision_policy_from_config(self._config),
        )
        scheduled = await self._deliveries.schedule_run(
            generated.persistence.run.id,
            rendered_at=datetime.now(timezone.utc),
        )
        result = MatchingDeliveryOutcome(
            opportunity_id=opportunity_id,
            matching=generated,
            delivery=scheduled,
        )
        try:
            shadow_report = await self._evidence_shadow_recorder.record_match_run(
                generated.persistence.traces,
            )
        except Exception as error:
            self._metrics.increment(
                MetricNames.MATCHING_EVIDENCE_SHADOW_FAILURES,
                tags={"error_type": type(error).__name__},
            )
            log_event(
                self._logger,
                logging.WARNING,
                "matching.opportunity_evidence_shadow_failed",
                match_run_id=generated.persistence.run.id,
                opportunity_id=opportunity_id,
                shadow_version="opportunity-evidence-shadow.v2",
                error_type=type(error).__name__,
            )
            shadow_report = None
        log_event(
            self._logger,
            logging.INFO,
            "matching.delivery_orchestration_completed",
            opportunity_id=opportunity_id,
            match_run_id=generated.persistence.run.id,
            match_run_created=generated.persistence.created,
            trace_count=len(generated.persistence.traces),
            eligible_match_count=generated.report.eligible_match_count,
            delivery_created_count=scheduled.created_count,
            delivery_reused_count=scheduled.reused_count,
            delivery_failure_count=len(scheduled.failures),
            user_specific_llm_calls=generated.report.user_specific_llm_calls,
            opportunity_analyzer_calls=generated.report.opportunity_analyzer_calls,
            evidence_shadow_attempted=(
                None if shadow_report is None else shadow_report.attempted
            ),
            evidence_shadow_created=(
                None if shadow_report is None else shadow_report.created
            ),
            evidence_shadow_reused=(
                None if shadow_report is None else shadow_report.reused
            ),
            evidence_shadow_failed=(
                None if shadow_report is None else shadow_report.failed
            ),
        )
        return result


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("durable matching job created_at must include a timezone")
    return value
