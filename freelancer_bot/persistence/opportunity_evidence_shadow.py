from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import json
import logging
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from ..metrics import MetricNames, MetricsSink, NoOpMetrics
from ..observability import log_event
from ..opportunity_evidence import (
    OPPORTUNITY_ANALYSIS_V2_SCHEMA_VERSION,
    OPPORTUNITY_EVIDENCE_ONTOLOGY_VERSION,
    OPPORTUNITY_EVIDENCE_SHADOW_VERSION,
    EvidenceAwareShadowTrace,
    OpportunityAnalysisV2,
    build_opportunity_analysis_v2,
    evidence_aware_shadow_trace,
)
from .database import Database
from .matches import MatchTraceRecord
from .opportunities import CanonicalOpportunityRecord, CanonicalOpportunityRepository
from .raw_messages import RawMessageRecord, RawMessageRepository
from .schema import opportunity_evidence_shadow_traces
from .search_profiles import SearchProfileRecord, SearchProfileRepository


OPPORTUNITY_EVIDENCE_SHADOW_TRACE_SCHEMA_VERSION = (
    "opportunity_evidence_shadow_trace.v1"
)
OPPORTUNITY_EVIDENCE_RAW_SOURCE_POLICY_VERSION = (
    "opportunity-evidence-raw-source.v1"
)


class OpportunityEvidenceShadowConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class OpportunityEvidenceShadowDraft:
    schema_version: str
    shadow_version: str
    ontology_version: str
    match_trace_id: UUID
    match_run_id: UUID
    opportunity_id: UUID
    search_profile_id: UUID
    profile_revision: int
    raw_message_id: UUID
    raw_source_policy_version: str
    raw_content_sha256: str
    current_decision_code: str
    current_eligible: bool
    current_combined_relevance_score: Decimal | None
    current_final_rank_score: Decimal | None
    shadow_decision: str
    shadow_score: Decimal
    generic_signal_blocked: bool
    shadow_payload: Mapping[str, Any]
    payload_sha256: str
    evaluated_at: datetime


@dataclass(frozen=True)
class OpportunityEvidenceShadowRecord(OpportunityEvidenceShadowDraft):
    id: UUID
    created_at: datetime


@dataclass(frozen=True)
class OpportunityEvidenceShadowPersistOutcome:
    record: OpportunityEvidenceShadowRecord
    created: bool


@dataclass(frozen=True)
class OpportunityEvidenceShadowRunReport:
    attempted: int
    created: int
    reused: int
    failed: int


class OpportunityEvidenceShadowRepository:
    async def persist(
        self,
        connection: AsyncConnection,
        draft: OpportunityEvidenceShadowDraft,
    ) -> OpportunityEvidenceShadowPersistOutcome:
        record_id = uuid4()
        inserted_id = await connection.scalar(
            pg_insert(opportunity_evidence_shadow_traces)
            .values(id=record_id, **_draft_values(draft))
            .on_conflict_do_nothing(
                constraint="uq_opportunity_evidence_shadow_traces_trace_version"
            )
            .returning(opportunity_evidence_shadow_traces.c.id)
        )
        record = await self.get(
            connection,
            match_trace_id=draft.match_trace_id,
            shadow_version=draft.shadow_version,
        )
        if record is None:
            raise OpportunityEvidenceShadowConflict(
                "Opportunity evidence shadow trace disappeared after persistence"
            )
        if record.payload_sha256 != draft.payload_sha256:
            raise OpportunityEvidenceShadowConflict(
                "Opportunity evidence shadow trace payload hash conflict"
            )
        return OpportunityEvidenceShadowPersistOutcome(
            record=record,
            created=inserted_id is not None,
        )

    async def get(
        self,
        connection: AsyncConnection,
        *,
        match_trace_id: UUID,
        shadow_version: str = OPPORTUNITY_EVIDENCE_SHADOW_VERSION,
    ) -> OpportunityEvidenceShadowRecord | None:
        row = (
            await connection.execute(
                sa.select(opportunity_evidence_shadow_traces).where(
                    opportunity_evidence_shadow_traces.c.match_trace_id
                    == match_trace_id,
                    opportunity_evidence_shadow_traces.c.shadow_version
                    == shadow_version,
                )
            )
        ).mappings().one_or_none()
        return None if row is None else _record(row)

    async def list_for_match_run(
        self,
        connection: AsyncConnection,
        match_run_id: UUID,
        *,
        limit: int = 1000,
    ) -> tuple[OpportunityEvidenceShadowRecord, ...]:
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        rows = (
            await connection.execute(
                sa.select(opportunity_evidence_shadow_traces)
                .where(
                    opportunity_evidence_shadow_traces.c.match_run_id
                    == match_run_id
                )
                .order_by(
                    opportunity_evidence_shadow_traces.c.created_at,
                    opportunity_evidence_shadow_traces.c.id,
                )
                .limit(limit)
            )
        ).mappings().all()
        return tuple(_record(row) for row in rows)

    async def list_for_opportunity(
        self,
        connection: AsyncConnection,
        opportunity_id: UUID,
        *,
        limit: int = 1000,
    ) -> tuple[OpportunityEvidenceShadowRecord, ...]:
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be between 1 and 5000")
        rows = (
            await connection.execute(
                sa.select(opportunity_evidence_shadow_traces)
                .where(
                    opportunity_evidence_shadow_traces.c.opportunity_id
                    == opportunity_id
                )
                .order_by(
                    opportunity_evidence_shadow_traces.c.created_at,
                    opportunity_evidence_shadow_traces.c.id,
                )
                .limit(limit)
            )
        ).mappings().all()
        return tuple(_record(row) for row in rows)


class OpportunityEvidenceShadowRecorder:
    def __init__(
        self,
        database: Database,
        *,
        shadows: OpportunityEvidenceShadowRepository | None = None,
        opportunities: CanonicalOpportunityRepository | None = None,
        raw_messages: RawMessageRepository | None = None,
        profiles: SearchProfileRepository | None = None,
        metrics: MetricsSink | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._database = database
        self._shadows = shadows or OpportunityEvidenceShadowRepository()
        self._opportunities = opportunities or CanonicalOpportunityRepository()
        self._raw_messages = raw_messages or RawMessageRepository()
        self._profiles = profiles or SearchProfileRepository()
        self._metrics = metrics or NoOpMetrics()
        self._logger = logger or logging.getLogger(__name__)

    async def record_match_run(
        self,
        traces: Sequence[MatchTraceRecord],
    ) -> OpportunityEvidenceShadowRunReport:
        attempted = len(traces)
        created = 0
        reused = 0
        failed = 0
        if attempted:
            self._metrics.increment(
                MetricNames.MATCHING_EVIDENCE_SHADOW_ATTEMPTED,
                attempted,
            )
        v2_cache: dict[UUID, tuple[OpportunityAnalysisV2, RawMessageRecord]] = {}
        for record in traces:
            try:
                outcome = await self._record_trace(record, v2_cache)
            except Exception as error:
                failed += 1
                self._metrics.increment(
                    MetricNames.MATCHING_EVIDENCE_SHADOW_FAILURES,
                    tags={"error_type": type(error).__name__},
                )
                log_event(
                    self._logger,
                    logging.WARNING,
                    "matching.opportunity_evidence_shadow_failed",
                    match_run_id=record.run_id,
                    match_trace_id=record.id,
                    opportunity_id=record.trace.opportunity_id,
                    search_profile_id=record.trace.search_profile_id,
                    profile_revision=record.trace.profile_revision,
                    shadow_version=OPPORTUNITY_EVIDENCE_SHADOW_VERSION,
                    error_type=type(error).__name__,
                )
                continue
            if outcome.created:
                created += 1
                self._metrics.increment(
                    MetricNames.MATCHING_EVIDENCE_SHADOW_CREATED
                )
                created_or_reused = "created"
            else:
                reused += 1
                self._metrics.increment(
                    MetricNames.MATCHING_EVIDENCE_SHADOW_REUSED
                )
                created_or_reused = "reused"
            self._metrics.increment(
                MetricNames.MATCHING_EVIDENCE_SHADOW_DECISIONS,
                tags={"decision": outcome.record.shadow_decision},
            )
            log_event(
                self._logger,
                logging.INFO,
                "matching.opportunity_evidence_shadow_recorded",
                match_run_id=outcome.record.match_run_id,
                match_trace_id=outcome.record.match_trace_id,
                opportunity_id=outcome.record.opportunity_id,
                search_profile_id=outcome.record.search_profile_id,
                profile_revision=outcome.record.profile_revision,
                raw_message_id=outcome.record.raw_message_id,
                shadow_version=outcome.record.shadow_version,
                shadow_decision=outcome.record.shadow_decision,
                shadow_score=str(outcome.record.shadow_score),
                generic_signal_blocked=outcome.record.generic_signal_blocked,
                created_or_reused=created_or_reused,
            )
        return OpportunityEvidenceShadowRunReport(
            attempted=attempted,
            created=created,
            reused=reused,
            failed=failed,
        )

    async def _record_trace(
        self,
        record: MatchTraceRecord,
        v2_cache: dict[UUID, tuple[OpportunityAnalysisV2, RawMessageRecord]],
    ) -> OpportunityEvidenceShadowPersistOutcome:
        trace = record.trace
        if trace.opportunity_id not in v2_cache:
            async with self._database.connect() as connection:
                opportunity = await self._opportunities.get(
                    connection,
                    trace.opportunity_id,
                )
                if opportunity is None:
                    raise LookupError("matched Opportunity does not exist")
                raw_message_id = select_opportunity_evidence_raw_message_id(
                    opportunity
                )
                raw = await self._raw_messages.get_by_id(connection, raw_message_id)
                if raw is None:
                    raise LookupError("shadow raw message does not exist")
            v2_cache[trace.opportunity_id] = (
                build_opportunity_analysis_v2(
                    opportunity.analysis,
                    raw_message_text=raw.content,
                ),
                raw,
            )
        analysis_v2, raw = v2_cache[trace.opportunity_id]
        async with self._database.connect() as connection:
            profile = await self._profiles.get(connection, trace.search_profile_id)
        if profile.revision != trace.profile_revision:
            raise RuntimeError("SearchProfile revision differs from match trace")
        shadow = evidence_aware_shadow_trace(analysis_v2, profile)
        draft = build_opportunity_evidence_shadow_draft(
            record,
            raw=raw,
            shadow=shadow,
            analysis=analysis_v2,
            profile=profile,
        )
        async with self._database.transaction() as connection:
            return await self._shadows.persist(connection, draft)


def select_opportunity_evidence_raw_message_id(
    opportunity: CanonicalOpportunityRecord,
) -> UUID:
    if opportunity.preferred_source is not None:
        return opportunity.preferred_source.raw_message_id
    if not opportunity.source_observations:
        raise LookupError("Opportunity has no linked source observations")
    return min(
        opportunity.source_observations,
        key=lambda item: (item.message_date, str(item.raw_message_id)),
    ).raw_message_id


def build_opportunity_evidence_shadow_draft(
    record: MatchTraceRecord,
    *,
    raw: RawMessageRecord,
    shadow: EvidenceAwareShadowTrace,
    analysis: OpportunityAnalysisV2,
    profile: SearchProfileRecord,
) -> OpportunityEvidenceShadowDraft:
    trace = record.trace
    if profile.id != trace.search_profile_id:
        raise ValueError("profile does not match trace")
    if profile.revision != trace.profile_revision:
        raise ValueError("profile revision does not match trace")
    raw_hash = sha256(raw.content.encode("utf-8")).hexdigest()
    payload = sanitize_opportunity_evidence_shadow_payload(
        shadow,
        analysis=analysis,
    )
    payload_hash = _payload_hash(payload)
    return OpportunityEvidenceShadowDraft(
        schema_version=OPPORTUNITY_EVIDENCE_SHADOW_TRACE_SCHEMA_VERSION,
        shadow_version=shadow.shadow_version,
        ontology_version=analysis.ontology_version,
        match_trace_id=record.id,
        match_run_id=record.run_id,
        opportunity_id=trace.opportunity_id,
        search_profile_id=trace.search_profile_id,
        profile_revision=trace.profile_revision,
        raw_message_id=raw.id,
        raw_source_policy_version=OPPORTUNITY_EVIDENCE_RAW_SOURCE_POLICY_VERSION,
        raw_content_sha256=raw_hash,
        current_decision_code=trace.decision_code.value,
        current_eligible=trace.eligible,
        current_combined_relevance_score=trace.combined_relevance_score,
        current_final_rank_score=trace.final_rank_score,
        shadow_decision=shadow.decision.value,
        shadow_score=shadow.score,
        generic_signal_blocked=shadow.generic_signal_blocked,
        shadow_payload=payload,
        payload_sha256=payload_hash,
        evaluated_at=trace.evaluated_at,
    )


def sanitize_opportunity_evidence_shadow_payload(
    shadow: EvidenceAwareShadowTrace,
    *,
    analysis: OpportunityAnalysisV2,
) -> dict[str, Any]:
    return {
        "schema_version": OPPORTUNITY_EVIDENCE_SHADOW_TRACE_SCHEMA_VERSION,
        "opportunity_analysis_schema_version": OPPORTUNITY_ANALYSIS_V2_SCHEMA_VERSION,
        "shadow_version": shadow.shadow_version,
        "ontology_version": analysis.ontology_version,
        "base_schema_version": analysis.base_schema_version,
        "evidence": [
            {
                "dimension": item.dimension.value,
                "concept_id": item.concept_id,
                "origin": item.origin.value,
                "verification": item.verification.value,
                "confidence": item.confidence.value,
                "polarity": item.polarity.value,
                "source": item.source.value,
                "field_path": item.field_path,
                "counts_as_positive": item.counts_as_positive,
                "authoritative": item.authoritative,
                "verifier_version": item.verifier_version,
            }
            for item in analysis.evidence
        ],
        "matches": [
            {
                "dimension": match.dimension.value,
                "concept_id": match.concept_id,
                "opportunity_origin": match.opportunity_origin.value,
                "profile_origin": match.profile_origin.value,
                "opportunity_verification": match.opportunity_verification.value,
                "profile_verification": match.profile_verification.value,
                "opportunity_confidence": match.opportunity_confidence.value,
                "profile_confidence": match.profile_confidence.value,
                "opportunity_polarity": match.opportunity_polarity.value,
                "profile_polarity": match.profile_polarity.value,
                "counts_as_positive": match.counts_as_positive,
            }
            for match in shadow.matches
        ],
        "decision": shadow.decision.value,
        "score": str(shadow.score),
        "generic_signal_blocked": shadow.generic_signal_blocked,
        "deduped_match_count": shadow.deduped_match_count,
        "independent_dimensions": list(shadow.independent_dimensions),
        "current_policy_changed": shadow.current_policy_changed,
        "shadow_weights_experimental": shadow.shadow_weights_experimental,
        "shadow_score_not_production_policy": (
            shadow.shadow_score_not_production_policy
        ),
    }


def _draft_values(draft: OpportunityEvidenceShadowDraft) -> dict[str, Any]:
    return {
        "schema_version": draft.schema_version,
        "shadow_version": draft.shadow_version,
        "ontology_version": draft.ontology_version,
        "match_trace_id": draft.match_trace_id,
        "match_run_id": draft.match_run_id,
        "opportunity_id": draft.opportunity_id,
        "search_profile_id": draft.search_profile_id,
        "profile_revision": draft.profile_revision,
        "raw_message_id": draft.raw_message_id,
        "raw_source_policy_version": draft.raw_source_policy_version,
        "raw_content_sha256": draft.raw_content_sha256,
        "current_decision_code": draft.current_decision_code,
        "current_eligible": draft.current_eligible,
        "current_combined_relevance_score": draft.current_combined_relevance_score,
        "current_final_rank_score": draft.current_final_rank_score,
        "shadow_decision": draft.shadow_decision,
        "shadow_score": draft.shadow_score,
        "generic_signal_blocked": draft.generic_signal_blocked,
        "shadow_payload": dict(draft.shadow_payload),
        "payload_sha256": draft.payload_sha256,
        "evaluated_at": draft.evaluated_at,
    }


def _record(row: Mapping[str, Any]) -> OpportunityEvidenceShadowRecord:
    return OpportunityEvidenceShadowRecord(
        id=row["id"],
        schema_version=str(row["schema_version"]),
        shadow_version=str(row["shadow_version"]),
        ontology_version=str(row["ontology_version"]),
        match_trace_id=row["match_trace_id"],
        match_run_id=row["match_run_id"],
        opportunity_id=row["opportunity_id"],
        search_profile_id=row["search_profile_id"],
        profile_revision=int(row["profile_revision"]),
        raw_message_id=row["raw_message_id"],
        raw_source_policy_version=str(row["raw_source_policy_version"]),
        raw_content_sha256=str(row["raw_content_sha256"]),
        current_decision_code=str(row["current_decision_code"]),
        current_eligible=bool(row["current_eligible"]),
        current_combined_relevance_score=_decimal(
            row["current_combined_relevance_score"]
        ),
        current_final_rank_score=_decimal(row["current_final_rank_score"]),
        shadow_decision=str(row["shadow_decision"]),
        shadow_score=Decimal(row["shadow_score"]),
        generic_signal_blocked=bool(row["generic_signal_blocked"]),
        shadow_payload=dict(row["shadow_payload"]),
        payload_sha256=str(row["payload_sha256"]),
        evaluated_at=row["evaluated_at"],
        created_at=row["created_at"],
    )


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return sha256(
        json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _decimal(value) -> Decimal | None:
    return None if value is None else Decimal(value)
