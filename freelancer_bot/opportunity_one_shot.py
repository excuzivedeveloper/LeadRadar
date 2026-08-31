from __future__ import annotations

import logging
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from .config import ConfigurationError, RuntimeConfig
from .ingestion_runtime import _configured_analyzer
from .message_prefilter import OPPORTUNITY_ANALYSIS_JOB_TYPE
from .observability import log_event
from .opportunity_classifier import OpportunityAnalysisJobProcessor
from .persistence.database import Database
from .persistence.jobs import DurableJobRepository
from .worker import DurableWorker, WorkerOptions


LOGGER = logging.getLogger("freelancer_bot")


class OpportunityAnalysisOneShotError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status: str = "rejected_before_claim",
        job_state: str | None = None,
        failure_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.job_state = job_state
        self.failure_code = failure_code


@dataclass(frozen=True)
class OpportunityAnalysisOneShotResult:
    job_id: UUID
    processed: bool
    state: str
    failure_code: str | None = None


async def run_opportunity_analysis_job_once(
    config: RuntimeConfig,
    job_id: UUID,
    *,
    database: Database | None = None,
    repository: DurableJobRepository | None = None,
    logger: logging.Logger | None = None,
) -> OpportunityAnalysisOneShotResult:
    close_database = database is None
    active_logger = logger or LOGGER
    db = database or Database(config.postgresql_url())
    jobs = repository or DurableJobRepository()
    try:
        await _require_claimable_opportunity_job(db, jobs, job_id)
        analyzer = _configured_analyzer(db, config)
        if analyzer is None:
            raise ConfigurationError(
                "Opportunity Analysis provider is not configured for one-shot job processing"
            )
        worker = DurableWorker(
            db,
            repository=jobs,
            worker_id=_one_shot_worker_id(),
            handlers={
                OPPORTUNITY_ANALYSIS_JOB_TYPE: OpportunityAnalysisJobProcessor(
                    db,
                    analyzer,
                    jobs=jobs,
                    logger=active_logger,
                )
            },
            logger=active_logger,
            options=WorkerOptions.from_config(config),
            close_database_on_exit=False,
            job_ids=(job_id,),
        )
        processed = await worker.run_one()
        if not processed:
            raise OpportunityAnalysisOneShotError(
                "Selected opportunity analysis job is not eligible for claim"
            )
        row = await _read_selected_job(db, jobs, job_id)
        state = str(row["state"])
        failure_code = row["failure_code"]
        if state == "completed":
            log_event(
                active_logger,
                logging.INFO,
                "opportunity.analysis.one_shot_completed",
                job_id=job_id,
                job_type=OPPORTUNITY_ANALYSIS_JOB_TYPE,
                state=state,
            )
            return OpportunityAnalysisOneShotResult(
                job_id=job_id,
                processed=True,
                state=state,
                failure_code=failure_code,
            )
        if state == "queued":
            log_event(
                active_logger,
                logging.WARNING,
                "opportunity.analysis.one_shot_retry_scheduled",
                job_id=job_id,
                job_type=OPPORTUNITY_ANALYSIS_JOB_TYPE,
                state=state,
                failure_code=failure_code,
            )
            raise OpportunityAnalysisOneShotError(
                "Selected opportunity analysis job scheduled retry",
                status="retry_queued",
                job_state=state,
                failure_code=failure_code,
            )
        if state == "failed":
            log_event(
                active_logger,
                logging.ERROR,
                "opportunity.analysis.one_shot_failed",
                job_id=job_id,
                job_type=OPPORTUNITY_ANALYSIS_JOB_TYPE,
                state=state,
                failure_code=failure_code,
            )
            raise OpportunityAnalysisOneShotError(
                "Selected opportunity analysis job failed",
                status="failed",
                job_state=state,
                failure_code=failure_code,
            )
        log_event(
            active_logger,
            logging.ERROR,
            "opportunity.analysis.one_shot_unexpected_state",
            job_id=job_id,
            job_type=OPPORTUNITY_ANALYSIS_JOB_TYPE,
            state=state,
            failure_code=failure_code,
        )
        raise OpportunityAnalysisOneShotError(
            "Selected opportunity analysis job reached unexpected state",
            status="unexpected_state",
            job_state=state,
            failure_code=failure_code,
        )
    finally:
        if close_database:
            await db.close()


async def _read_selected_job(
    database: Database,
    repository: DurableJobRepository,
    job_id: UUID,
):
    async with database.connect() as connection:
        row = await repository.get(connection, job_id)
    if row is None:
        raise OpportunityAnalysisOneShotError(
            "Selected opportunity analysis job disappeared",
            status="unexpected_state",
        )
    return row


async def _require_claimable_opportunity_job(
    database: Database,
    repository: DurableJobRepository,
    job_id: UUID,
) -> None:
    async with database.connect() as connection:
        row = await repository.get(connection, job_id)
    if row is None:
        raise OpportunityAnalysisOneShotError("Selected durable job does not exist")
    if row["job_type"] != OPPORTUNITY_ANALYSIS_JOB_TYPE:
        raise OpportunityAnalysisOneShotError(
            "Selected durable job is not opportunity.analysis.v1"
        )
    if row["state"] == "completed":
        raise OpportunityAnalysisOneShotError(
            "Selected opportunity analysis job is already completed"
        )
    if row["state"] == "failed":
        raise OpportunityAnalysisOneShotError(
            "Selected opportunity analysis job is terminally failed"
        )
    if int(row["attempt_count"]) >= int(row["max_attempts"]):
        raise OpportunityAnalysisOneShotError(
            "Selected opportunity analysis job has exhausted attempts"
        )
    now = datetime.now(timezone.utc)
    if row["state"] == "queued":
        available_at = _aware(row["available_at"])
        if available_at > now:
            raise OpportunityAnalysisOneShotError(
                "Selected opportunity analysis job is not yet eligible"
            )
        return
    if row["state"] == "running":
        lease_expires_at = _aware(row["lease_expires_at"])
        if lease_expires_at > now:
            raise OpportunityAnalysisOneShotError(
                "Selected opportunity analysis job has an unexpired lease"
            )
        return
    raise OpportunityAnalysisOneShotError(
        "Selected opportunity analysis job has an unsupported state"
    )


def _aware(value: datetime | None) -> datetime:
    if value is None:
        return datetime.max.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _one_shot_worker_id() -> str:
    return f"opportunity-one-shot-{socket.gethostname()}-{uuid4().hex[:8]}"
