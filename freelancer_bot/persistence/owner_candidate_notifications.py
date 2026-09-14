from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import re
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from .schema import (
    owner_source_candidate_notification_scan_state,
    owner_source_candidate_notifications,
    owner_source_candidate_probe_state,
    source_profile_relevance,
    sources,
)
from .source_repository import (
    SourceRecord,
    SourceStatus,
    _select_sources,
    _source_record,
)


_TELEGRAM_HANDLE_RE = re.compile(r"^@?[a-zA-Z][a-zA-Z0-9_]{4,31}$")


class OwnerSourceCandidateReservationStatus(str, Enum):
    RESERVED = "reserved"
    ALREADY_NOTIFIED = "already_notified"
    SOURCE_NOT_FOUND = "source_not_found"
    NOT_CANDIDATE = "not_candidate"
    IDENTITY_CHANGED = "identity_changed"


class OwnerSourceCandidateProbeOutcome(str, Enum):
    STALE_OR_EMPTY = "stale_or_empty"
    UNRESOLVABLE = "unresolvable"


STALE_OR_EMPTY_COOLDOWN_HOURS = 24
UNRESOLVABLE_BACKOFF_HOURS = (6, 12, 24, 48)


@dataclass(frozen=True)
class OwnerSourceCandidateSelection:
    candidates: tuple[SourceRecord, ...]
    cooldown_suppressed: int


@dataclass(frozen=True)
class OwnerSourceCandidateProbeState:
    consecutive_outcomes: int
    next_probe_at: datetime


@dataclass(frozen=True)
class OwnerSourceCandidateNotificationReservation:
    id: int
    source: SourceRecord


@dataclass(frozen=True)
class OwnerSourceCandidateReservationResult:
    status: OwnerSourceCandidateReservationStatus
    reservation: OwnerSourceCandidateNotificationReservation | None = None


class OwnerSourceCandidateNotificationRepository:
    async def list_unnotified_candidates(
        self,
        connection: AsyncConnection,
        *,
        recipient_chat_id: int,
        search_profile_id: UUID,
        discovery_intent_id: UUID,
        profile_revision: int,
        relevance_class: str,
        selection_now: datetime,
        limit: int,
    ) -> OwnerSourceCandidateSelection:
        if recipient_chat_id <= 0:
            raise ValueError("recipient_chat_id must be positive")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if profile_revision < 1:
            raise ValueError("profile_revision must be positive")
        if relevance_class != "strong":
            raise ValueError("candidate notification relevance_class must be strong")
        if selection_now.tzinfo is None or selection_now.utcoffset() is None:
            raise ValueError("selection_now must be timezone-aware")
        cooldown_suppressed = await self._cooldown_suppressed_count(
            connection,
            recipient_chat_id=recipient_chat_id,
            search_profile_id=search_profile_id,
            discovery_intent_id=discovery_intent_id,
            profile_revision=profile_revision,
            relevance_class=relevance_class,
            selection_now=selection_now,
        )
        cursor = await self._scan_cursor(connection, recipient_chat_id)
        rows = await self._candidate_page(
            connection,
            recipient_chat_id=recipient_chat_id,
            search_profile_id=search_profile_id,
            discovery_intent_id=discovery_intent_id,
            profile_revision=profile_revision,
            relevance_class=relevance_class,
            selection_now=selection_now,
            after_source_id=cursor,
            limit=limit,
        )
        if not rows and cursor is not None:
            rows = await self._candidate_page(
                connection,
                recipient_chat_id=recipient_chat_id,
                search_profile_id=search_profile_id,
                discovery_intent_id=discovery_intent_id,
                profile_revision=profile_revision,
                relevance_class=relevance_class,
                selection_now=selection_now,
                after_source_id=None,
                limit=limit,
            )
        records = tuple(_source_record(row) for row in rows)
        if records:
            await self._set_scan_cursor(
                connection,
                recipient_chat_id=recipient_chat_id,
                last_source_id=records[-1].id,
            )
        return OwnerSourceCandidateSelection(records, cooldown_suppressed)

    async def _candidate_page(
        self,
        connection: AsyncConnection,
        *,
        recipient_chat_id: int,
        search_profile_id: UUID,
        discovery_intent_id: UUID,
        profile_revision: int,
        relevance_class: str,
        selection_now: datetime,
        after_source_id: int | None,
        limit: int,
    ):
        notified = sa.exists(
            sa.select(1).where(
                owner_source_candidate_notifications.c.recipient_chat_id
                == recipient_chat_id,
                owner_source_candidate_notifications.c.source_id == sources.c.id,
            )
        )
        current_relevance = sa.exists(
            sa.select(1).where(
                source_profile_relevance.c.source_id == sources.c.id,
                source_profile_relevance.c.search_profile_id == search_profile_id,
                source_profile_relevance.c.discovery_intent_id
                == discovery_intent_id,
                source_profile_relevance.c.profile_revision == profile_revision,
                source_profile_relevance.c.relevance_class == relevance_class,
            )
        )
        cooling = sa.exists(
            sa.select(1).where(
                owner_source_candidate_probe_state.c.recipient_chat_id
                == recipient_chat_id,
                owner_source_candidate_probe_state.c.source_id == sources.c.id,
                owner_source_candidate_probe_state.c.search_profile_id
                == search_profile_id,
                owner_source_candidate_probe_state.c.discovery_intent_id
                == discovery_intent_id,
                owner_source_candidate_probe_state.c.profile_revision
                == profile_revision,
                owner_source_candidate_probe_state.c.next_probe_at > selection_now,
            )
        )
        statement = (
            _select_sources(True)
            .where(
                sources.c.platform == "telegram",
                sources.c.lifecycle_status == SourceStatus.CANDIDATE.value,
                current_relevance,
                ~notified,
                ~cooling,
            )
            .order_by(sources.c.id)
            .limit(limit)
        )
        if after_source_id is not None:
            statement = statement.where(sources.c.id > after_source_id)
        rows = await connection.execute(statement)
        return rows.mappings().all()

    async def _cooldown_suppressed_count(
        self,
        connection: AsyncConnection,
        *,
        recipient_chat_id: int,
        search_profile_id: UUID,
        discovery_intent_id: UUID,
        profile_revision: int,
        relevance_class: str,
        selection_now: datetime,
    ) -> int:
        notified = sa.exists(
            sa.select(1).where(
                owner_source_candidate_notifications.c.recipient_chat_id
                == recipient_chat_id,
                owner_source_candidate_notifications.c.source_id == sources.c.id,
            )
        )
        current_relevance = sa.exists(
            sa.select(1).where(
                source_profile_relevance.c.source_id == sources.c.id,
                source_profile_relevance.c.search_profile_id == search_profile_id,
                source_profile_relevance.c.discovery_intent_id
                == discovery_intent_id,
                source_profile_relevance.c.profile_revision == profile_revision,
                source_profile_relevance.c.relevance_class == relevance_class,
            )
        )
        cooling = sa.exists(
            sa.select(1).where(
                owner_source_candidate_probe_state.c.recipient_chat_id
                == recipient_chat_id,
                owner_source_candidate_probe_state.c.source_id == sources.c.id,
                owner_source_candidate_probe_state.c.search_profile_id
                == search_profile_id,
                owner_source_candidate_probe_state.c.discovery_intent_id
                == discovery_intent_id,
                owner_source_candidate_probe_state.c.profile_revision
                == profile_revision,
                owner_source_candidate_probe_state.c.next_probe_at > selection_now,
            )
        )
        count = await connection.scalar(
            sa.select(sa.func.count())
            .select_from(sources)
            .where(
                sources.c.platform == "telegram",
                sources.c.lifecycle_status == SourceStatus.CANDIDATE.value,
                current_relevance,
                ~notified,
                cooling,
            )
        )
        return int(count or 0)

    async def record_probe_outcome(
        self,
        connection: AsyncConnection,
        *,
        recipient_chat_id: int,
        source_id: int,
        search_profile_id: UUID,
        discovery_intent_id: UUID,
        profile_revision: int,
        outcome: OwnerSourceCandidateProbeOutcome,
        probed_at: datetime,
    ) -> OwnerSourceCandidateProbeState:
        if recipient_chat_id <= 0 or source_id <= 0:
            raise ValueError("recipient_chat_id and source_id must be positive")
        if profile_revision < 1:
            raise ValueError("profile_revision must be positive")
        if probed_at.tzinfo is None or probed_at.utcoffset() is None:
            raise ValueError("probed_at must be timezone-aware")
        initial_delay = (
            timedelta(hours=STALE_OR_EMPTY_COOLDOWN_HOURS)
            if outcome is OwnerSourceCandidateProbeOutcome.STALE_OR_EMPTY
            else timedelta(hours=UNRESOLVABLE_BACKOFF_HOURS[0])
        )
        statement = pg_insert(owner_source_candidate_probe_state).values(
            recipient_chat_id=recipient_chat_id,
            source_id=source_id,
            search_profile_id=search_profile_id,
            discovery_intent_id=discovery_intent_id,
            profile_revision=profile_revision,
            last_outcome=outcome.value,
            consecutive_outcomes=1,
            last_probed_at=probed_at,
            next_probe_at=probed_at + initial_delay,
            created_at=probed_at,
            updated_at=probed_at,
        )
        excluded = statement.excluded
        same_binding_outcome = sa.and_(
            owner_source_candidate_probe_state.c.search_profile_id
            == excluded.search_profile_id,
            owner_source_candidate_probe_state.c.discovery_intent_id
            == excluded.discovery_intent_id,
            owner_source_candidate_probe_state.c.profile_revision
            == excluded.profile_revision,
            owner_source_candidate_probe_state.c.last_outcome == excluded.last_outcome,
        )
        next_probe_at = sa.case(
            (
                excluded.last_outcome
                == OwnerSourceCandidateProbeOutcome.STALE_OR_EMPTY.value,
                excluded.last_probed_at
                + _postgres_interval_hours(STALE_OR_EMPTY_COOLDOWN_HOURS),
            ),
            (
                ~same_binding_outcome,
                excluded.last_probed_at
                + _postgres_interval_hours(UNRESOLVABLE_BACKOFF_HOURS[0]),
            ),
            (
                owner_source_candidate_probe_state.c.consecutive_outcomes == 1,
                excluded.last_probed_at
                + _postgres_interval_hours(UNRESOLVABLE_BACKOFF_HOURS[1]),
            ),
            (
                owner_source_candidate_probe_state.c.consecutive_outcomes == 2,
                excluded.last_probed_at
                + _postgres_interval_hours(UNRESOLVABLE_BACKOFF_HOURS[2]),
            ),
            else_=excluded.last_probed_at
            + _postgres_interval_hours(UNRESOLVABLE_BACKOFF_HOURS[3]),
        )
        upsert = statement.on_conflict_do_update(
            index_elements=[
                owner_source_candidate_probe_state.c.recipient_chat_id,
                owner_source_candidate_probe_state.c.source_id,
            ],
            set_={
                "search_profile_id": excluded.search_profile_id,
                "discovery_intent_id": excluded.discovery_intent_id,
                "profile_revision": excluded.profile_revision,
                "last_outcome": excluded.last_outcome,
                "consecutive_outcomes": sa.case(
                    (
                        same_binding_outcome,
                        owner_source_candidate_probe_state.c.consecutive_outcomes + 1,
                    ),
                    else_=1,
                ),
                "last_probed_at": excluded.last_probed_at,
                "next_probe_at": next_probe_at,
                "updated_at": excluded.updated_at,
            },
        ).returning(
            owner_source_candidate_probe_state.c.consecutive_outcomes,
            owner_source_candidate_probe_state.c.next_probe_at,
        )
        row = (await connection.execute(upsert)).one()
        return OwnerSourceCandidateProbeState(
            consecutive_outcomes=int(row.consecutive_outcomes),
            next_probe_at=row.next_probe_at,
        )

    async def clear_probe_state(
        self,
        connection: AsyncConnection,
        *,
        recipient_chat_id: int,
        source_id: int,
        search_profile_id: UUID,
        discovery_intent_id: UUID,
        profile_revision: int,
    ) -> None:
        await connection.execute(
            sa.delete(owner_source_candidate_probe_state).where(
                owner_source_candidate_probe_state.c.recipient_chat_id
                == recipient_chat_id,
                owner_source_candidate_probe_state.c.source_id == source_id,
                owner_source_candidate_probe_state.c.search_profile_id
                == search_profile_id,
                owner_source_candidate_probe_state.c.discovery_intent_id
                == discovery_intent_id,
                owner_source_candidate_probe_state.c.profile_revision
                == profile_revision,
            )
        )

    async def _scan_cursor(
        self,
        connection: AsyncConnection,
        recipient_chat_id: int,
    ) -> int | None:
        return await connection.scalar(
            sa.select(
                owner_source_candidate_notification_scan_state.c.last_source_id
            ).where(
                owner_source_candidate_notification_scan_state.c.recipient_chat_id
                == recipient_chat_id
            )
        )

    async def _set_scan_cursor(
        self,
        connection: AsyncConnection,
        *,
        recipient_chat_id: int,
        last_source_id: int,
    ) -> None:
        statement = pg_insert(owner_source_candidate_notification_scan_state).values(
            recipient_chat_id=recipient_chat_id,
            last_source_id=last_source_id,
            updated_at=sa.func.now(),
        )
        await connection.execute(
            statement.on_conflict_do_update(
                index_elements=[
                    owner_source_candidate_notification_scan_state.c.recipient_chat_id
                ],
                set_={
                    "last_source_id": last_source_id,
                    "updated_at": sa.func.now(),
                },
            )
        )

    async def reserve(
        self,
        connection: AsyncConnection,
        *,
        source_id: int,
        recipient_chat_id: int,
        source_identity_snapshot: dict[str, Any],
        source_url_snapshot: str,
        expected_handle: str | None,
        expected_canonical_url: str | None,
        latest_message_at: datetime,
        attempted_at: datetime,
    ) -> OwnerSourceCandidateReservationResult:
        if source_id <= 0:
            raise ValueError("source_id must be positive")
        if recipient_chat_id <= 0:
            raise ValueError("recipient_chat_id must be positive")
        row = (
            await connection.execute(
                _select_sources(True)
                .where(sources.c.id == source_id)
                .with_for_update()
            )
        ).mappings().one_or_none()
        if row is None:
            return OwnerSourceCandidateReservationResult(
                OwnerSourceCandidateReservationStatus.SOURCE_NOT_FOUND
            )
        source = _source_record(row)
        if (
            source.platform != "telegram"
            or source.lifecycle_status != SourceStatus.CANDIDATE
        ):
            return OwnerSourceCandidateReservationResult(
                OwnerSourceCandidateReservationStatus.NOT_CANDIDATE
            )
        if not _identity_matches(
            source,
            expected_handle=expected_handle,
            expected_canonical_url=expected_canonical_url,
        ):
            return OwnerSourceCandidateReservationResult(
                OwnerSourceCandidateReservationStatus.IDENTITY_CHANGED
            )

        statement = (
            pg_insert(owner_source_candidate_notifications)
            .values(
                source_id=source_id,
                recipient_chat_id=recipient_chat_id,
                source_identity_snapshot=source_identity_snapshot,
                source_url_snapshot=source_url_snapshot,
                latest_message_at=latest_message_at,
                status="reserved",
                attempted_at=attempted_at,
                created_at=attempted_at,
                updated_at=attempted_at,
            )
            .on_conflict_do_nothing(
                constraint="uq_owner_source_candidate_notifications_recipient_source"
            )
            .returning(owner_source_candidate_notifications.c.id)
        )
        notification_id = await connection.scalar(statement)
        if notification_id is None:
            return OwnerSourceCandidateReservationResult(
                OwnerSourceCandidateReservationStatus.ALREADY_NOTIFIED
            )
        return OwnerSourceCandidateReservationResult(
            OwnerSourceCandidateReservationStatus.RESERVED,
            OwnerSourceCandidateNotificationReservation(
                id=int(notification_id),
                source=source,
            ),
        )

    async def mark_sent(
        self,
        connection: AsyncConnection,
        *,
        notification_id: int,
        telegram_message_id: int,
        sent_at: datetime,
    ) -> None:
        if notification_id <= 0:
            raise ValueError("notification_id must be positive")
        if telegram_message_id <= 0:
            raise ValueError("telegram_message_id must be positive")
        await connection.execute(
            sa.update(owner_source_candidate_notifications)
            .where(owner_source_candidate_notifications.c.id == notification_id)
            .values(
                status="sent",
                telegram_message_id=telegram_message_id,
                sent_at=sent_at,
                updated_at=sent_at,
            )
        )

    async def mark_failed(
        self,
        connection: AsyncConnection,
        *,
        notification_id: int,
        failure_code: str,
        failed_at: datetime,
    ) -> None:
        if notification_id <= 0:
            raise ValueError("notification_id must be positive")
        if not failure_code or failure_code.strip() != failure_code:
            raise ValueError("failure_code must be normalized")
        await connection.execute(
            sa.update(owner_source_candidate_notifications)
            .where(owner_source_candidate_notifications.c.id == notification_id)
            .values(
                status="failed",
                failure_code=failure_code,
                updated_at=failed_at,
            )
        )


def _identity_matches(
    source: SourceRecord,
    *,
    expected_handle: str | None,
    expected_canonical_url: str | None,
) -> bool:
    current_handle = _safe_handle(source.handle)
    if expected_handle is not None:
        return current_handle == expected_handle
    if current_handle is not None:
        return False
    return _safe_telegram_channel_url(source.canonical_url) == expected_canonical_url


def _safe_telegram_channel_url(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() not in {"t.me", "telegram.me"}:
        return None
    if parsed.query or parsed.fragment:
        return None
    handle = _safe_handle(parsed.path.strip("/"))
    if handle is None:
        return None
    return f"https://t.me/{handle}"


def _safe_handle(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not _TELEGRAM_HANDLE_RE.fullmatch(candidate):
        return None
    return candidate.removeprefix("@")


def _postgres_interval_hours(hours: int):
    return sa.func.make_interval(0, 0, 0, 0, hours)
