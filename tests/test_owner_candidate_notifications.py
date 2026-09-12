from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from uuid import UUID

from freelancer_bot.config import RuntimeConfig
from freelancer_bot.owner_candidate_notifications import (
    OwnerCandidateNotificationService,
    telegram_candidate_address,
    telegram_source_url,
)
from freelancer_bot.profile_discovery import build_profile_discovery_intent
from freelancer_bot.persistence.owner_candidate_notifications import (
    OwnerSourceCandidateNotificationReservation,
    OwnerSourceCandidateReservationResult,
    OwnerSourceCandidateReservationStatus,
)
from freelancer_bot.persistence.source_repository import SourceRecord, SourceStatus
from freelancer_bot.persistence.search_profiles import (
    SearchProfileConfirmationStatus,
    UserNotFound,
)
from freelancer_bot.telegram_request_governor import TelegramRequestCategory


NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
OWNER_ID = 7000001
OWNER_USER_ID = UUID("10000000-0000-0000-0000-000000000001")
PROFILE_ID = UUID("20000000-0000-0000-0000-000000000001")
OTHER_PROFILE_ID = UUID("20000000-0000-0000-0000-000000000002")


class OwnerCandidateNotificationServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_profile_gate_observability_binds_current_owner_intent(self):
        repository = _Repository(candidates=[])

        summary = await _service(repository).run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW),
            bot_client=_BotClient(),
            governor=_Governor(),
        )

        intent = build_profile_discovery_intent(_profile())
        self.assertTrue(summary.profile_gate_ready)
        self.assertEqual(summary.profile_id, PROFILE_ID)
        self.assertEqual(summary.profile_revision, 3)
        self.assertEqual(summary.discovery_intent_id, intent.id)
        self.assertEqual(summary.relevance_gate, "strong")
        self.assertIn("PROFILE_GATE_READY=YES", summary.as_lines())
        self.assertEqual(repository.last_gate["discovery_intent_id"], intent.id)

    async def test_missing_owner_user_fails_closed_before_query_or_telegram(self):
        repository = _Repository(candidates=[_source(20)])
        governor = _Governor()

        summary = await _service(repository, owner_exists=False).run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW),
            bot_client=_BotClient(),
            governor=governor,
        )

        self.assertFalse(summary.profile_gate_ready)
        self.assertEqual(repository.list_calls, 0)
        self.assertEqual(governor.categories, [])

    async def test_missing_or_ambiguous_current_profile_fails_closed(self):
        for profiles in ((), (_profile(), _profile(profile_id=OTHER_PROFILE_ID))):
            repository = _Repository(candidates=[_source(21)])
            governor = _Governor()
            summary = await _service(repository, profiles=profiles).run_once(
                config=_config(),
                collector_account_id=11,
                user_client=_UserClient(message_date=NOW),
                bot_client=_BotClient(),
                governor=governor,
            )
            self.assertFalse(summary.profile_gate_ready)
            self.assertEqual(repository.list_calls, 0)
            self.assertEqual(governor.categories, [])

    async def test_only_exact_current_strong_relevance_reaches_telegram(self):
        profile = _profile()
        intent_id = build_profile_discovery_intent(profile).id
        sources = [_source(source_id) for source_id in range(30, 36)]
        rows = [
            (30, PROFILE_ID, intent_id, 3, "strong"),
            (31, PROFILE_ID, intent_id, 3, "adequate"),
            (32, PROFILE_ID, intent_id, 3, "weak"),
            (32, PROFILE_ID, UUID(int=32), 2, "strong"),
            (33, PROFILE_ID, UUID(int=33), 2, "strong"),
            (34, OTHER_PROFILE_ID, intent_id, 3, "strong"),
            (35, PROFILE_ID, UUID(int=35), 3, "strong"),
        ]
        repository = _Repository(candidates=sources, relevance_rows=rows)
        governor = _Governor()
        bot = _BotClient()

        summary = await _service(repository).run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW),
            bot_client=bot,
            governor=governor,
            limit=1,
        )

        self.assertEqual(summary.candidates_considered, 1)
        self.assertEqual(summary.sent, 1)
        self.assertEqual(repository.reserved_source_ids, [30])
        self.assertEqual(len(governor.categories), 2)
        self.assertEqual(len(bot.calls), 1)

    async def test_non_current_or_non_strong_relevance_never_reaches_telegram(self):
        profile = _profile()
        intent_id = build_profile_discovery_intent(profile).id
        cases = {
            "adequate": [(70, PROFILE_ID, intent_id, 3, "adequate")],
            "weak": [(70, PROFILE_ID, intent_id, 3, "weak")],
            "missing": [],
            "historical_strong_current_weak": [
                (70, PROFILE_ID, UUID(int=70), 2, "strong"),
                (70, PROFILE_ID, intent_id, 3, "weak"),
            ],
            "historical_strong_without_current": [
                (70, PROFILE_ID, UUID(int=70), 2, "strong"),
            ],
            "other_profile": [
                (70, OTHER_PROFILE_ID, UUID(int=71), 3, "strong"),
            ],
            "old_revision": [
                (70, PROFILE_ID, UUID(int=72), 2, "strong"),
            ],
        }

        for label, rows in cases.items():
            with self.subTest(label=label):
                repository = _Repository(
                    candidates=[_source(70)], relevance_rows=rows
                )
                governor = _Governor()
                bot = _BotClient()
                summary = await _service(repository).run_once(
                    config=_config(),
                    collector_account_id=11,
                    user_client=_UserClient(message_date=NOW),
                    bot_client=bot,
                    governor=governor,
                )
                self.assertEqual(summary.candidates_considered, 0)
                self.assertEqual(governor.categories, [])
                self.assertEqual(repository.reserved_source_ids, [])
                self.assertEqual(bot.calls, [])

    async def test_relevance_filter_is_applied_before_limit(self):
        profile = _profile()
        intent_id = build_profile_discovery_intent(profile).id
        sources = [_source(source_id) for source_id in range(40, 52)]
        rows = [
            *(
                (source.id, PROFILE_ID, intent_id, 3, "weak")
                for source in sources[:-1]
            ),
            (sources[-1].id, PROFILE_ID, intent_id, 3, "strong"),
        ]
        repository = _Repository(candidates=sources, relevance_rows=rows)

        summary = await _service(repository).run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW),
            bot_client=_BotClient(),
            governor=_Governor(),
            limit=1,
        )

        self.assertEqual(summary.candidates_considered, 1)
        self.assertEqual(repository.reserved_source_ids, [51])

    async def test_cursor_wrap_finds_newly_strong_candidate_behind_cursor(self):
        profile = _profile()
        intent_id = build_profile_discovery_intent(profile).id
        behind = _source(50, handle="@behind_cursor")
        first_source = _source(60, handle="@first_cursor")
        repository = _Repository(
            candidates=[behind, first_source],
            relevance_rows=[(60, PROFILE_ID, intent_id, 3, "strong")],
        )
        service = _service(repository)

        first = await service.run_once(
            config=_config(), collector_account_id=11,
            user_client=_UserClient(message_date=NOW), bot_client=_BotClient(),
            governor=_Governor(), limit=1,
        )
        repository.relevance_rows.append((50, PROFILE_ID, intent_id, 3, "strong"))
        second = await service.run_once(
            config=_config(), collector_account_id=11,
            user_client=_UserClient(message_date=NOW), bot_client=_BotClient(),
            governor=_Governor(), limit=1,
        )

        self.assertEqual(first.sent, 1)
        self.assertEqual(second.sent, 1)
        self.assertEqual(repository.reserved_source_ids, [60, 50])

    async def test_fresh_candidate_at_ten_days_sends_once_with_url_button(self):
        source = _source(
            1,
            display_name="RU Jobs",
            handle="@ru_jobs",
            canonical_url="https://t.me/ru_jobs",
            language="ru",
        )
        repository = _Repository(candidates=[source])
        bot = _BotClient()
        service = _service(repository)

        summary = await service.run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW - timedelta(days=10)),
            bot_client=bot,
            governor=_Governor(),
        )

        self.assertEqual(summary.fresh_within_10_days, 1)
        self.assertEqual(summary.reserved, 1)
        self.assertEqual(summary.sent, 1)
        self.assertEqual(repository.reserved_source_ids, [1])
        self.assertEqual(repository.sent_ids, [1])
        self.assertEqual(len(bot.calls), 1)
        call = bot.calls[0]
        self.assertEqual(call["chat_id"], OWNER_ID)
        self.assertIn("RU Jobs", call["body"])
        self.assertIn("RU", call["body"])
        self.assertIn("Последнее сообщение", call["body"])
        self.assertNotIn("Approve", call["body"])
        self.assertNotIn("Reject", call["body"])
        self.assertEqual(
            call["buttons"],
            [[("url", "📲 Открыть канал", "https://t.me/ru_jobs")]],
        )

    async def test_stale_candidate_does_not_create_marker_and_can_become_fresh_later(self):
        source = _source(2, handle="@later_fresh")
        repository = _Repository(candidates=[source])
        service = _service(repository)

        stale = await service.run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW - timedelta(days=10, seconds=1)),
            bot_client=_BotClient(),
            governor=_Governor(),
        )
        fresh = await service.run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW - timedelta(days=1)),
            bot_client=_BotClient(),
            governor=_Governor(),
        )

        self.assertEqual(stale.stale_or_empty, 1)
        self.assertEqual(stale.reserved, 0)
        self.assertEqual(fresh.sent, 1)
        self.assertEqual(repository.reserved_source_ids, [2])

    async def test_no_messages_does_not_notify_or_reserve(self):
        source = _source(13, handle="@empty_source")
        repository = _Repository(candidates=[source])

        summary = await _service(repository).run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=None),
            bot_client=_BotClient(),
            governor=_Governor(),
        )

        self.assertEqual(summary.stale_or_empty, 1)
        self.assertEqual(summary.reserved, 0)
        self.assertEqual(repository.reserved_source_ids, [])

    async def test_non_candidate_source_from_repository_fails_closed(self):
        source = _source(14, handle="@approved_source", status=SourceStatus.APPROVED)
        repository = _Repository(candidates=[source])
        governor = _Governor()
        bot = _BotClient()

        summary = await _service(repository).run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW),
            bot_client=bot,
            governor=governor,
        )

        self.assertEqual(summary.candidates_considered, 1)
        self.assertEqual(summary.activity_probes, 0)
        self.assertEqual(repository.reserved_source_ids, [])
        self.assertEqual(bot.calls, [])

    async def test_existing_attempt_suppresses_future_automatic_sends_even_after_failure(self):
        source = _source(3, handle="@send_failure")
        repository = _Repository(candidates=[source])
        bot = _BotClient(fail=True)
        service = _service(repository)

        first = await service.run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW),
            bot_client=bot,
            governor=_Governor(),
        )
        second = await service.run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW),
            bot_client=_BotClient(),
            governor=_Governor(),
        )

        self.assertEqual(first.failed, 1)
        self.assertEqual(repository.failed_ids, [1])
        self.assertEqual(second.candidates_considered, 0)
        self.assertEqual(second.sent, 0)

    async def test_handle_change_same_source_id_does_not_resend(self):
        first = _source(15, handle="@first_handle")
        second = _source(15, handle="@second_handle")
        repository = _Repository(candidates=[first])
        service = _service(repository)

        await service.run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW),
            bot_client=_BotClient(),
            governor=_Governor(),
        )
        repository.candidates = [second]
        summary = await service.run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW),
            bot_client=_BotClient(),
            governor=_Governor(),
        )

        self.assertEqual(summary.candidates_considered, 0)
        self.assertEqual(repository.reserved_source_ids, [15])

    async def test_backlog_cursor_reaches_fresh_candidate_behind_stale_batch(self):
        stale_sources = [
            _source(source_id, handle=f"@source_{source_id}")
            for source_id in range(1, 11)
        ]
        fresh_source = _source(11, handle="@source_11")
        repository = _Repository(candidates=[*stale_sources, fresh_source])
        service = _service(repository)

        first = await service.run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_MappedUserClient(
                {source.id: NOW - timedelta(days=20) for source in stale_sources}
                | {fresh_source.id: NOW}
            ),
            bot_client=_BotClient(),
            governor=_Governor(),
            limit=10,
        )
        second = await service.run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_MappedUserClient(
                {source.id: NOW - timedelta(days=20) for source in stale_sources}
                | {fresh_source.id: NOW}
            ),
            bot_client=_BotClient(),
            governor=_Governor(),
            limit=10,
        )

        self.assertEqual(first.stale_or_empty, 10)
        self.assertEqual(first.sent, 0)
        self.assertEqual(second.candidates_considered, 1)
        self.assertEqual(second.sent, 1)
        self.assertEqual(repository.reserved_source_ids, [11])

    async def test_handle_identity_drives_probe_and_button_when_canonical_differs(self):
        source = _source(
            16,
            handle="@new_handle",
            canonical_url="https://t.me/old_handle",
        )
        bot = _BotClient()
        user = _UserClient(message_date=NOW)

        summary = await _service(_Repository(candidates=[source])).run_once(
            config=_config(),
            collector_account_id=11,
            user_client=user,
            bot_client=bot,
            governor=_Governor(),
        )

        self.assertEqual(summary.sent, 1)
        self.assertEqual(user.lookups, ["new_handle"])
        self.assertEqual(
            bot.calls[0]["buttons"],
            [[("url", "📲 Открыть канал", "https://t.me/new_handle")]],
        )

    async def test_identity_change_before_reserve_fails_closed_without_marker(self):
        source = _source(17, handle="@before_race")
        repository = _Repository(
            candidates=[source],
            reserve_status=OwnerSourceCandidateReservationStatus.IDENTITY_CHANGED,
        )
        bot = _BotClient()

        summary = await _service(repository).run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW),
            bot_client=bot,
            governor=_Governor(),
        )

        self.assertEqual(summary.identity_changed, 1)
        self.assertEqual(summary.already_notified, 0)
        self.assertEqual(summary.sent, 0)
        self.assertEqual(repository.reserved_source_ids, [])
        self.assertEqual(bot.calls, [])

    async def test_owner_not_configured_fails_closed_before_probe_or_send(self):
        source = _source(4, handle="@ownerless")
        repository = _Repository(candidates=[source])
        governor = _Governor()
        bot = _BotClient()

        summary = await _service(repository).run_once(
            config=RuntimeConfig(_env_file=None),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW),
            bot_client=bot,
            governor=governor,
        )

        self.assertEqual(summary.candidates_considered, 0)
        self.assertEqual(repository.list_calls, 0)
        self.assertEqual(governor.categories, [])
        self.assertEqual(bot.calls, [])

    async def test_unresolvable_and_no_safe_url_candidates_are_not_notified(self):
        sources = [
            _source(5, handle=None, canonical_url="https://example.com/channel"),
            _source(6, handle="@bad", canonical_url=None),
        ]
        repository = _Repository(candidates=sources)

        summary = await _service(repository).run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW),
            bot_client=_BotClient(),
            governor=_Governor(),
        )

        self.assertEqual(summary.unresolvable, 2)
        self.assertEqual(summary.activity_probes, 0)
        self.assertEqual(repository.reserved_source_ids, [])

    async def test_entity_resolution_failure_counts_unresolvable(self):
        source = _source(12, handle="@missing_source")
        repository = _Repository(candidates=[source])

        summary = await _service(repository).run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW, resolve_fails=True),
            bot_client=_BotClient(),
            governor=_Governor(),
        )

        self.assertEqual(summary.activity_probes, 1)
        self.assertEqual(summary.unresolvable, 1)
        self.assertEqual(summary.stale_or_empty, 0)
        self.assertEqual(repository.reserved_source_ids, [])

    async def test_lifecycle_race_after_probe_does_not_send(self):
        source = _source(7, handle="@race_source")
        repository = _Repository(
            candidates=[source],
            reserve_status=OwnerSourceCandidateReservationStatus.NOT_CANDIDATE,
        )
        bot = _BotClient()

        summary = await _service(repository).run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW),
            bot_client=bot,
            governor=_Governor(),
        )

        self.assertEqual(summary.fresh_within_10_days, 1)
        self.assertEqual(summary.already_notified, 0)
        self.assertEqual(summary.no_longer_candidate, 1)
        self.assertEqual(summary.sent, 0)
        self.assertEqual(bot.calls, [])

    async def test_true_duplicate_reservation_counts_already_notified(self):
        source = _source(18, handle="@duplicate_source")
        repository = _Repository(
            candidates=[source],
            reserve_status=OwnerSourceCandidateReservationStatus.ALREADY_NOTIFIED,
        )

        summary = await _service(repository).run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW),
            bot_client=_BotClient(),
            governor=_Governor(),
        )

        self.assertEqual(summary.already_notified, 1)
        self.assertEqual(summary.no_longer_candidate, 0)
        self.assertEqual(summary.identity_changed, 0)

    async def test_activity_probe_uses_entity_and_history_governor_categories(self):
        source = _source(8, handle="@governed_source")
        governor = _Governor()

        await _service(_Repository(candidates=[source])).run_once(
            config=_config(),
            collector_account_id=11,
            user_client=_UserClient(message_date=NOW),
            bot_client=_BotClient(),
            governor=governor,
        )

        self.assertEqual(
            governor.categories,
            [
                TelegramRequestCategory.ENTITY_ACCESS,
                TelegramRequestCategory.HISTORY,
            ],
        )

    def test_safe_url_prefers_valid_handle_and_rejects_provider_urls(self):
        self.assertEqual(
            telegram_source_url(
                _source(
                    9,
                    handle="@fallback_handle",
                    canonical_url="https://t.me/canonical_handle",
                )
            ),
            "https://t.me/fallback_handle",
        )
        self.assertEqual(
            telegram_source_url(
                _source(
                    10,
                    handle="@fallback_handle",
                    canonical_url="https://provider.test/not-telegram",
                )
            ),
            "https://t.me/fallback_handle",
        )
        self.assertIsNone(
            telegram_source_url(
                _source(11, handle=None, canonical_url="https://provider.test/x")
            )
        )
        address = telegram_candidate_address(
            _source(19, handle=None, canonical_url="https://t.me/canonical_handle")
        )
        self.assertIsNotNone(address)
        self.assertEqual(address.lookup, "https://t.me/canonical_handle")
        self.assertEqual(address.url, "https://t.me/canonical_handle")


def _service(
    repository: _Repository,
    *,
    owner_exists: bool = True,
    profiles=None,
) -> OwnerCandidateNotificationService:
    return OwnerCandidateNotificationService(
        _Database(),
        repository=repository,
        user_repository=_UserRepository(owner_exists=owner_exists),
        search_profile_repository=_SearchProfileRepository(
            profiles=(_profile(),) if profiles is None else profiles
        ),
        clock=lambda: NOW,
        button_factory=lambda label, url: ("url", label, url),
    )


def _config() -> RuntimeConfig:
    return RuntimeConfig(_env_file=None, owner_telegram_user_id=OWNER_ID)


def _source(
    source_id: int,
    *,
    display_name: str = "Candidate",
    handle: str | None = "@candidate_source",
    canonical_url: str | None = "https://t.me/candidate_source",
    language: str | None = None,
    status: SourceStatus = SourceStatus.CANDIDATE,
) -> SourceRecord:
    return SourceRecord(
        id=source_id,
        platform="telegram",
        external_id=f"username:source_{source_id}",
        access_type="public",
        lifecycle_status=status,
        display_name=display_name,
        handle=handle,
        canonical_url=canonical_url,
        language=language,
        language_origin=None,
        language_conflict=False,
        created_at=NOW,
        updated_at=NOW,
    )


class _Database:
    @asynccontextmanager
    async def connect(self):
        yield object()

    @asynccontextmanager
    async def transaction(self):
        yield object()


class _Repository:
    def __init__(
        self,
        *,
        candidates: list[SourceRecord],
        reserve_status: OwnerSourceCandidateReservationStatus
        | None = OwnerSourceCandidateReservationStatus.RESERVED,
        relevance_rows=None,
    ) -> None:
        self.candidates = list(candidates)
        self.reserve_status = reserve_status
        self.relevance_rows = relevance_rows
        self.last_gate = None
        self.list_calls = 0
        self.reserved_source_ids: list[int] = []
        self.sent_ids: list[int] = []
        self.failed_ids: list[int] = []
        self._attempted_source_ids: set[int] = set()
        self._next_id = 1
        self._cursor: int | None = None

    async def list_unnotified_candidates(
        self,
        _connection,
        *,
        recipient_chat_id: int,
        search_profile_id,
        discovery_intent_id,
        profile_revision: int,
        relevance_class: str,
        limit: int,
    ):
        self.list_calls += 1
        self.last_gate = {
            "search_profile_id": search_profile_id,
            "discovery_intent_id": discovery_intent_id,
            "profile_revision": profile_revision,
            "relevance_class": relevance_class,
        }
        unnotified = [
            source
            for source in self.candidates
            if source.id not in self._attempted_source_ids
            and (
                self.relevance_rows is None
                or (
                    source.id,
                    search_profile_id,
                    discovery_intent_id,
                    profile_revision,
                    relevance_class,
                ) in self.relevance_rows
            )
        ]
        after_cursor = [
            source
            for source in unnotified
            if self._cursor is None or source.id > self._cursor
        ]
        selected = after_cursor[:limit]
        if not selected and self._cursor is not None:
            selected = unnotified[:limit]
        if selected:
            self._cursor = selected[-1].id
        return tuple(selected)

    async def reserve(
        self,
        _connection,
        *,
        source_id: int,
        recipient_chat_id: int,
        source_identity_snapshot: dict,
        source_url_snapshot: str,
        expected_handle: str | None,
        expected_canonical_url: str | None,
        latest_message_at: datetime,
        attempted_at: datetime,
    ):
        if (
            self.reserve_status
            is not OwnerSourceCandidateReservationStatus.RESERVED
        ):
            return OwnerSourceCandidateReservationResult(self.reserve_status)
        if source_id in self._attempted_source_ids:
            return OwnerSourceCandidateReservationResult(
                OwnerSourceCandidateReservationStatus.ALREADY_NOTIFIED
            )
        self._attempted_source_ids.add(source_id)
        self.reserved_source_ids.append(source_id)
        notification_id = self._next_id
        self._next_id += 1
        source = next(source for source in self.candidates if source.id == source_id)
        return OwnerSourceCandidateReservationResult(
            OwnerSourceCandidateReservationStatus.RESERVED,
            OwnerSourceCandidateNotificationReservation(
                id=notification_id,
                source=source,
            ),
        )

    async def mark_sent(
        self,
        _connection,
        *,
        notification_id: int,
        telegram_message_id: int,
        sent_at: datetime,
    ) -> None:
        self.sent_ids.append(notification_id)

    async def mark_failed(
        self,
        _connection,
        *,
        notification_id: int,
        failure_code: str,
        failed_at: datetime,
    ) -> None:
        self.failed_ids.append(notification_id)


class _UserRepository:
    def __init__(self, *, owner_exists: bool) -> None:
        self.owner_exists = owner_exists

    async def get_by_identity(
        self,
        _connection,
        *,
        platform: str,
        external_user_id: str,
    ):
        if not self.owner_exists:
            raise UserNotFound("missing owner")
        assert platform == "telegram"
        assert external_user_id == str(OWNER_ID)
        return SimpleNamespace(id=OWNER_USER_ID)


class _SearchProfileRepository:
    def __init__(self, *, profiles) -> None:
        self.profiles = tuple(profiles)

    async def list_for_user(self, _connection, *, user_id):
        assert user_id == OWNER_USER_ID
        return self.profiles


def _profile(*, profile_id=PROFILE_ID, revision: int = 3):
    term = lambda value: SimpleNamespace(value=value)
    return SimpleNamespace(
        id=profile_id,
        user_id=OWNER_USER_ID,
        revision=revision,
        roles=(term("Python developer"),),
        skills=(term("FastAPI"),),
        categories=(term("backend development"),),
        semantic_text_normalized="python backend developer",
        preferences=SimpleNamespace(languages=(), geographies=(), work_modes=()),
        confirmation_status=SearchProfileConfirmationStatus.CONFIRMED,
        is_active=True,
        is_primary=True,
    )


class _Governor:
    def __init__(self) -> None:
        self.categories: list[str] = []

    async def run(self, category: str, operation, **_kwargs):
        self.categories.append(category)
        return await operation()


class _UserClient:
    def __init__(
        self,
        *,
        message_date: datetime | None,
        resolve_fails: bool = False,
    ) -> None:
        self.message_date = message_date
        self.resolve_fails = resolve_fails
        self.lookups: list[str] = []

    async def get_entity(self, lookup: str):
        self.lookups.append(lookup)
        if self.resolve_fails:
            raise ValueError("cannot resolve")
        return SimpleNamespace(lookup=lookup)

    def iter_messages(self, _entity, *, limit: int):
        async def messages():
            if self.message_date is not None:
                yield SimpleNamespace(date=self.message_date)

        return messages()


class _MappedUserClient:
    def __init__(self, messages_by_source_id: dict[int, datetime | None]) -> None:
        self.messages_by_source_id = messages_by_source_id

    async def get_entity(self, lookup: str):
        source_id = int(str(lookup).rsplit("_", 1)[1])
        return SimpleNamespace(source_id=source_id)

    def iter_messages(self, entity, *, limit: int):
        async def messages():
            message_date = self.messages_by_source_id[entity.source_id]
            if message_date is not None:
                yield SimpleNamespace(date=message_date)

        return messages()


class _BotClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict] = []

    async def send_message(self, chat_id: int, body: str, **kwargs):
        self.calls.append({"chat_id": chat_id, "body": body, **kwargs})
        if self.fail:
            raise RuntimeError("send failed")
        return SimpleNamespace(id=9001)


if __name__ == "__main__":
    unittest.main()
