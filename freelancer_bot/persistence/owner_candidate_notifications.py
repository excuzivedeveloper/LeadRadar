from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re
from typing import Any
from urllib.parse import urlparse

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from .schema import (
    owner_source_candidate_notification_scan_state,
    owner_source_candidate_notifications,
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
        limit: int,
    ) -> tuple[SourceRecord, ...]:
        if recipient_chat_id <= 0:
            raise ValueError("recipient_chat_id must be positive")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        cursor = await self._scan_cursor(connection, recipient_chat_id)
        rows = await self._candidate_page(
            connection,
            recipient_chat_id=recipient_chat_id,
            after_source_id=cursor,
            limit=limit,
        )
        if not rows and cursor is not None:
            rows = await self._candidate_page(
                connection,
                recipient_chat_id=recipient_chat_id,
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
        return records

    async def _candidate_page(
        self,
        connection: AsyncConnection,
        *,
        recipient_chat_id: int,
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
        statement = (
            _select_sources(True)
            .where(
                sources.c.platform == "telegram",
                sources.c.lifecycle_status == SourceStatus.CANDIDATE.value,
                ~notified,
            )
            .order_by(sources.c.id)
            .limit(limit)
        )
        if after_source_id is not None:
            statement = statement.where(sources.c.id > after_source_id)
        rows = await connection.execute(statement)
        return rows.mappings().all()

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
