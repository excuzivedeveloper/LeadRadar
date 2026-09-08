from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from .schema import owner_source_candidate_notifications, sources
from .source_repository import (
    SourceRecord,
    SourceStatus,
    _select_sources,
    _source_record,
)


@dataclass(frozen=True)
class OwnerSourceCandidateNotificationReservation:
    id: int
    source: SourceRecord


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
            .order_by(sources.c.updated_at.desc(), sources.c.id)
            .limit(limit)
        )
        rows = await connection.execute(statement)
        return tuple(_source_record(row) for row in rows.mappings())

    async def reserve(
        self,
        connection: AsyncConnection,
        *,
        source_id: int,
        recipient_chat_id: int,
        source_identity_snapshot: dict[str, Any],
        source_url_snapshot: str,
        latest_message_at: datetime,
        attempted_at: datetime,
    ) -> OwnerSourceCandidateNotificationReservation | None:
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
            return None
        source = _source_record(row)
        if (
            source.platform != "telegram"
            or source.lifecycle_status != SourceStatus.CANDIDATE
        ):
            return None

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
            return None
        return OwnerSourceCandidateNotificationReservation(
            id=int(notification_id),
            source=source,
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
