from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from freelancer_bot.config import RuntimeConfig
from freelancer_bot.owner_candidate_notifications import (
    OwnerCandidateNotificationService,
)
from freelancer_bot.profile_discovery import (
    ProfileDiscoveryIntentRepository,
    build_profile_discovery_intent,
)
from freelancer_bot.persistence.database import Database
from freelancer_bot.persistence.owner_candidate_notifications import (
    OwnerSourceCandidateNotificationRepository,
    OwnerSourceCandidateReservationStatus,
)
from freelancer_bot.persistence.schema import (
    owner_source_candidate_notifications,
    profile_discovery_intents,
    search_profiles,
    source_profile_relevance,
    sources,
    users,
)
from freelancer_bot.persistence.search_profiles import SearchProfileRepository
from freelancer_bot.persistence.source_repository import SourceStatus
from freelancer_bot.telegram_request_governor import TelegramRequestCategory
from postgres_support import TEST_DATABASE_URL, migrate_to_head, temporary_database


NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
OWNER_ID = 7000001
OTHER_OWNER_ID = 7000002
OWNER_USER_ID = UUID("10000000-0000-0000-0000-000000000001")
PROFILE_ID = UUID("20000000-0000-0000-0000-000000000001")


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not configured")
class OwnerCandidateNotificationsPostgresTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.database_context = temporary_database()
        self.database_url = self.database_context.__enter__()
        migrate_to_head(self.database_url)
        self.database = Database(self.database_url, pool_size=6, max_overflow=8)
        self.repository = OwnerSourceCandidateNotificationRepository()

    async def asyncSetUp(self) -> None:
        async with self.database.transaction() as connection:
            await connection.execute(
                users.insert().values(
                    id=OWNER_USER_ID,
                    platform="telegram",
                    external_user_id=str(OWNER_ID),
                )
            )
            await connection.execute(
                search_profiles.insert().values(
                    id=PROFILE_ID,
                    user_id=OWNER_USER_ID,
                    schema_version="search_profile.v1",
                    parser_version="search-profile-parser.v1",
                    roles=[_term("Python developer")],
                    skills=[_term("FastAPI")],
                    categories=[_term("backend development")],
                    semantic_text_original="python backend developer",
                    semantic_text_normalized="python backend developer",
                    confirmation_status="confirmed",
                    confirmed_at=NOW,
                    revision=3,
                    is_active=True,
                    is_primary=True,
                    activated_at=NOW,
                )
            )
            profile = await SearchProfileRepository().get(connection, PROFILE_ID)
            intent = build_profile_discovery_intent(profile)
            await ProfileDiscoveryIntentRepository().ensure(connection, intent)
            self.intent_id = intent.id

    async def asyncTearDown(self) -> None:
        await self.database.close()
        self.database_context.__exit__(None, None, None)

    async def test_scan_cursor_reaches_fresh_candidate_after_stale_batch(self):
        stale_ids: list[int] = []
        async with self.database.transaction() as connection:
            for index in range(1, 11):
                stale_ids.append(
                    await _insert_source(connection, handle=f"@pg_stale_{index}")
                )
            fresh_id = await _insert_source(connection, handle="@pg_fresh_11")

        bot = _BotClient()
        service = _service(self.database, self.repository)
        message_dates = {
            source_id: NOW - timedelta(days=20)
            for source_id in stale_ids
        }
        message_dates[fresh_id] = NOW

        first = await service.run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_MappedUserClient(message_dates),
            bot_client=bot,
            governor=_Governor(),
            limit=10,
        )
        second = await service.run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_MappedUserClient(message_dates),
            bot_client=bot,
            governor=_Governor(),
            limit=10,
        )

        self.assertEqual(first.stale_or_empty, 10)
        self.assertEqual(first.sent, 0)
        self.assertEqual(second.sent, 1)
        self.assertEqual(bot.sent_source_urls, ["https://t.me/pg_fresh_11"])

    async def test_relevance_filter_precedes_page_limit(self):
        async with self.database.transaction() as connection:
            for index in range(1, 11):
                await _insert_source(
                    connection,
                    handle=f"@pg_weak_{index}",
                    relevance_class="weak",
                )
            strong_id = await _insert_source(connection, handle="@pg_strong_11")
            candidates = await self.repository.list_unnotified_candidates(
                connection,
                recipient_chat_id=OWNER_ID,
                search_profile_id=PROFILE_ID,
                discovery_intent_id=self.intent_id,
                profile_revision=3,
                relevance_class="strong",
                limit=5,
            )

        self.assertEqual([source.id for source in candidates], [strong_id])

    async def test_stale_candidate_remains_reprobe_eligible_after_wrap(self):
        async with self.database.transaction() as connection:
            source_id = await _insert_source(connection, handle="@pg_later_1")

        service = _service(self.database, self.repository)
        stale = await service.run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_MappedUserClient({source_id: NOW - timedelta(days=20)}),
            bot_client=_BotClient(),
            governor=_Governor(),
            limit=10,
        )
        fresh_bot = _BotClient()
        fresh = await service.run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_MappedUserClient({source_id: NOW}),
            bot_client=fresh_bot,
            governor=_Governor(),
            limit=10,
        )

        self.assertEqual(stale.stale_or_empty, 1)
        self.assertEqual(stale.reserved, 0)
        self.assertEqual(fresh.sent, 1)

    async def test_persisted_dedupe_survives_repository_recreation_for_terminal_states(self):
        async with self.database.transaction() as connection:
            reserved_source = await _insert_source(connection, handle="@pg_reserved")
            sent_source = await _insert_source(connection, handle="@pg_sent")
            failed_source = await _insert_source(connection, handle="@pg_failed")
            reserved = await self.repository.reserve(
                connection,
                source_id=reserved_source,
                recipient_chat_id=OWNER_ID,
                source_identity_snapshot={"source": "reserved"},
                source_url_snapshot="https://t.me/pg_reserved",
                expected_handle="pg_reserved",
                expected_canonical_url=None,
                latest_message_at=NOW,
                attempted_at=NOW,
            )
            sent = await self.repository.reserve(
                connection,
                source_id=sent_source,
                recipient_chat_id=OWNER_ID,
                source_identity_snapshot={"source": "sent"},
                source_url_snapshot="https://t.me/pg_sent",
                expected_handle="pg_sent",
                expected_canonical_url=None,
                latest_message_at=NOW,
                attempted_at=NOW,
            )
            failed = await self.repository.reserve(
                connection,
                source_id=failed_source,
                recipient_chat_id=OWNER_ID,
                source_identity_snapshot={"source": "failed"},
                source_url_snapshot="https://t.me/pg_failed",
                expected_handle="pg_failed",
                expected_canonical_url=None,
                latest_message_at=NOW,
                attempted_at=NOW,
            )
            await self.repository.mark_sent(
                connection,
                notification_id=sent.reservation.id,
                telegram_message_id=9001,
                sent_at=NOW,
            )
            await self.repository.mark_failed(
                connection,
                notification_id=failed.reservation.id,
                failure_code="test_send_failed",
                failed_at=NOW,
            )

        self.assertEqual(
            reserved.status,
            OwnerSourceCandidateReservationStatus.RESERVED,
        )
        recreated = OwnerSourceCandidateNotificationRepository()
        async with self.database.transaction() as connection:
            candidates = await recreated.list_unnotified_candidates(
                connection,
                recipient_chat_id=OWNER_ID,
                search_profile_id=PROFILE_ID,
                discovery_intent_id=self.intent_id,
                profile_revision=3,
                relevance_class="strong",
                limit=10,
            )

        self.assertEqual(candidates, ())

    async def test_concurrent_reservation_allows_exactly_one_row(self):
        async with self.database.transaction() as connection:
            source_id = await _insert_source(connection, handle="@pg_concurrent")

        async def reserve_once():
            async with self.database.transaction() as connection:
                return await OwnerSourceCandidateNotificationRepository().reserve(
                    connection,
                    source_id=source_id,
                    recipient_chat_id=OWNER_ID,
                    source_identity_snapshot={"source": "concurrent"},
                    source_url_snapshot="https://t.me/pg_concurrent",
                    expected_handle="pg_concurrent",
                    expected_canonical_url=None,
                    latest_message_at=NOW,
                    attempted_at=NOW,
                )

        first, second = await asyncio.gather(reserve_once(), reserve_once())
        statuses = {first.status, second.status}

        self.assertEqual(
            statuses,
            {
                OwnerSourceCandidateReservationStatus.RESERVED,
                OwnerSourceCandidateReservationStatus.ALREADY_NOTIFIED,
            },
        )
        async with self.database.connect() as connection:
            count = await connection.scalar(
                sa.select(sa.func.count()).select_from(
                    owner_source_candidate_notifications
                )
            )
        self.assertEqual(count, 1)

    async def test_unique_boundary_is_recipient_and_source(self):
        async with self.database.transaction() as connection:
            source_id = await _insert_source(connection, handle="@pg_unique")
            first = await self.repository.reserve(
                connection,
                source_id=source_id,
                recipient_chat_id=OWNER_ID,
                source_identity_snapshot={"source": "unique"},
                source_url_snapshot="https://t.me/pg_unique",
                expected_handle="pg_unique",
                expected_canonical_url=None,
                latest_message_at=NOW,
                attempted_at=NOW,
            )
            duplicate = await self.repository.reserve(
                connection,
                source_id=source_id,
                recipient_chat_id=OWNER_ID,
                source_identity_snapshot={"source": "unique"},
                source_url_snapshot="https://t.me/pg_unique",
                expected_handle="pg_unique",
                expected_canonical_url=None,
                latest_message_at=NOW,
                attempted_at=NOW,
            )
            other_recipient = await self.repository.reserve(
                connection,
                source_id=source_id,
                recipient_chat_id=OTHER_OWNER_ID,
                source_identity_snapshot={"source": "unique"},
                source_url_snapshot="https://t.me/pg_unique",
                expected_handle="pg_unique",
                expected_canonical_url=None,
                latest_message_at=NOW,
                attempted_at=NOW,
            )

        self.assertEqual(first.status, OwnerSourceCandidateReservationStatus.RESERVED)
        self.assertEqual(
            duplicate.status,
            OwnerSourceCandidateReservationStatus.ALREADY_NOTIFIED,
        )
        self.assertEqual(
            other_recipient.status,
            OwnerSourceCandidateReservationStatus.RESERVED,
        )

    async def test_status_payload_constraints_reject_invalid_combinations(self):
        async with self.database.transaction() as connection:
            source_id = await _insert_source(connection, handle="@pg_constraints")
            reserved = await self.repository.reserve(
                connection,
                source_id=source_id,
                recipient_chat_id=OWNER_ID,
                source_identity_snapshot={"source": "constraints"},
                source_url_snapshot="https://t.me/pg_constraints",
                expected_handle="pg_constraints",
                expected_canonical_url=None,
                latest_message_at=NOW,
                attempted_at=NOW,
            )
        self.assertEqual(reserved.status, OwnerSourceCandidateReservationStatus.RESERVED)

        invalid_values = [
            {"status": "reserved", "telegram_message_id": 1},
            {"status": "reserved", "failure_code": "bad"},
            {"status": "sent", "sent_at": NOW},
            {"status": "sent", "telegram_message_id": 1},
            {
                "status": "sent",
                "telegram_message_id": 1,
                "sent_at": NOW,
                "failure_code": "bad",
            },
            {"status": "failed"},
            {"status": "failed", "failure_code": "bad", "sent_at": NOW},
        ]
        for index, values in enumerate(invalid_values, start=1):
            with self.assertRaises(IntegrityError):
                async with self.database.transaction() as connection:
                    await _insert_notification(
                        connection,
                        source_id=source_id,
                        recipient_chat_id=OWNER_ID + index,
                        **values,
                    )

        async with self.database.transaction() as connection:
            sent_id = await _insert_source(connection, handle="@pg_constraints_sent")
            failed_id = await _insert_source(connection, handle="@pg_constraints_fail")
            await _insert_notification(
                connection,
                source_id=sent_id,
                recipient_chat_id=OWNER_ID,
                status="sent",
                telegram_message_id=9002,
                sent_at=NOW,
            )
            await _insert_notification(
                connection,
                source_id=failed_id,
                recipient_chat_id=OWNER_ID,
                status="failed",
                failure_code="test_failed",
            )

    async def test_non_candidate_locked_source_is_not_reserved(self):
        async with self.database.transaction() as connection:
            source_id = await _insert_source(connection, handle="@pg_lifecycle")
            await connection.execute(
                sa.update(sources)
                .where(sources.c.id == source_id)
                .values(lifecycle_status=SourceStatus.APPROVED.value)
            )
            result = await self.repository.reserve(
                connection,
                source_id=source_id,
                recipient_chat_id=OWNER_ID,
                source_identity_snapshot={"source": "lifecycle"},
                source_url_snapshot="https://t.me/pg_lifecycle",
                expected_handle="pg_lifecycle",
                expected_canonical_url=None,
                latest_message_at=NOW,
                attempted_at=NOW,
            )

        self.assertEqual(result.status, OwnerSourceCandidateReservationStatus.NOT_CANDIDATE)

    async def test_metadata_identity_change_rejects_reservation_without_marker(self):
        async with self.database.transaction() as connection:
            source_id = await _insert_source(connection, handle="@pg_before_change")
            await connection.execute(
                sa.update(sources)
                .where(sources.c.id == source_id)
                .values(handle="@pg_after_change")
            )
            result = await self.repository.reserve(
                connection,
                source_id=source_id,
                recipient_chat_id=OWNER_ID,
                source_identity_snapshot={"source": "identity"},
                source_url_snapshot="https://t.me/pg_before_change",
                expected_handle="pg_before_change",
                expected_canonical_url=None,
                latest_message_at=NOW,
                attempted_at=NOW,
            )
            row_count = await connection.scalar(
                sa.select(sa.func.count()).select_from(
                    owner_source_candidate_notifications
                )
            )

        self.assertEqual(result.status, OwnerSourceCandidateReservationStatus.IDENTITY_CHANGED)
        self.assertEqual(row_count, 0)


def _service(
    database: Database,
    repository: OwnerSourceCandidateNotificationRepository,
) -> OwnerCandidateNotificationService:
    return OwnerCandidateNotificationService(
        database,
        repository=repository,
        clock=lambda: NOW,
        button_factory=lambda label, url: ("url", label, url),
    )


def _config() -> RuntimeConfig:
    return RuntimeConfig(_env_file=None, owner_telegram_user_id=OWNER_ID)


async def _insert_source(
    connection,
    *,
    handle: str,
    relevance_class: str = "strong",
) -> int:
    source_id = await connection.scalar(
        sources.insert()
        .values(
            platform="telegram",
            external_id=f"username:{handle.removeprefix('@')}",
            access_type="public",
            lifecycle_status=SourceStatus.CANDIDATE.value,
            display_name=handle.removeprefix("@").replace("_", " ").title(),
            handle=handle,
            canonical_url=f"https://t.me/{handle.removeprefix('@')}",
        )
        .returning(sources.c.id)
    )
    intent_id = await connection.scalar(
        sa.select(profile_discovery_intents.c.id).where(
            profile_discovery_intents.c.search_profile_id == PROFILE_ID,
            profile_discovery_intents.c.profile_revision == 3,
        )
    )
    await connection.execute(
        source_profile_relevance.insert().values(
            source_id=source_id,
            search_profile_id=PROFILE_ID,
            discovery_intent_id=intent_id,
            profile_revision=3,
            relevance_score=("0.90000" if relevance_class == "strong" else "0.10000"),
            relevance_class=relevance_class,
            evidence_categories=["direct_profession"],
            last_evaluated_at=NOW,
            version="source-profile-relevance.v2",
        )
    )
    return int(source_id)


def _term(value: str) -> dict[str, str]:
    return {
        "value": value,
        "normalized_value": value.casefold(),
        "origin": "explicit",
        "evidence": value,
    }


async def _insert_notification(
    connection,
    *,
    source_id: int,
    recipient_chat_id: int,
    status: str,
    telegram_message_id: int | None = None,
    sent_at: datetime | None = None,
    failure_code: str | None = None,
) -> None:
    await connection.execute(
        owner_source_candidate_notifications.insert().values(
            source_id=source_id,
            recipient_chat_id=recipient_chat_id,
            source_identity_snapshot={"source_id": source_id},
            source_url_snapshot=f"https://t.me/source_{source_id}",
            latest_message_at=NOW,
            status=status,
            telegram_message_id=telegram_message_id,
            attempted_at=NOW,
            sent_at=sent_at,
            failure_code=failure_code,
        )
    )


class _Governor:
    async def run(self, category: str, operation, **_kwargs):
        self.category = category
        return await operation()


class _MappedUserClient:
    def __init__(self, messages_by_source_id: dict[int, datetime | None]) -> None:
        self.messages_by_source_id = messages_by_source_id

    async def get_entity(self, lookup: str):
        source_id = int(str(lookup).rsplit("_", 1)[1])
        return SimpleNamespace(source_id=source_id)

    def iter_messages(self, entity, *, limit: int):
        async def messages():
            self.last_limit = limit
            message_date = self.messages_by_source_id[entity.source_id]
            if message_date is not None:
                yield SimpleNamespace(date=message_date)

        return messages()


class _BotClient:
    def __init__(self) -> None:
        self.sent_source_urls: list[str] = []

    async def send_message(self, _chat_id: int, _body: str, **kwargs):
        self.sent_source_urls.append(kwargs["buttons"][0][0][2])
        return SimpleNamespace(id=9001)


if __name__ == "__main__":
    unittest.main()
